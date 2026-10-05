import asyncio
import signal
import sys
import os
import MetaTrader5 as mt5

from src.core.config import setup_logger, run_mt5_task
import src.core.config as config
from src.core.event_bus import EventBus
from src.core.campaign_ledger import CampaignLedger

# Core Engines
from src.core.telemetry import TelemetryLogger
from src.analytics.tearsheet import TearsheetGenerator
from src.core.broadcaster import TelegramBroadcaster
from src.execution.bridge import MT5Bridge
from src.execution.risk_manager import RiskManager
from src.execution.tick_sentinel import TickSentinel
from src.core.alpha import AlphaScorer, RegimeRadar
from src.analytics.ml_oracle import MLOracle

# Orchestrator
from src.strategy.alpha_harvester import AlphaHarvesterStrategy

logger = setup_logger("main")

async def shutdown(orchestrator: AlphaHarvesterStrategy, ledger: CampaignLedger, telemetry: TelemetryLogger = None, broadcaster: TelegramBroadcaster = None, tuner=None):
    logger.info("Initiating Graceful Shutdown...")
    if orchestrator:
        orchestrator.stop()
    if tuner:
        tuner.stop()
    
    if ledger:
        logger.info("Flushing SQLite State Ledger...")
        try:
            # Reconcile or flush logic if exposed by CampaignLedger
            pass
        except Exception as e:
            logger.error(f"Error flushing ledger: {e}")

    logger.info("Closing MT5 connections...")
    mt5.shutdown()
    
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    
    logger.info("Cancelling outstanding background tasks...")
    await asyncio.gather(*tasks, return_exceptions=True)
    if telemetry:
        await telemetry.stop()
    if broadcaster:
        await broadcaster.stop()
    logger.info("Graceful shutdown complete.")

async def main():
    logger.info("Initializing AUREXIS V2 Central Orchestrator Boot Sequence...")
    event_bus = EventBus()
    

    
    # State Ledger
    from src.database.ledger import Ledger
    db = Ledger(event_bus)
    await db.initialize()
    
    campaign_ledger = CampaignLedger(event_bus)
    await campaign_ledger.initialize()
    await campaign_ledger.load_and_reconcile()
    campaign_ledger.start_realtime_reconciliation()

    telemetry = TelemetryLogger()
    await telemetry.start()

    broadcaster = TelegramBroadcaster(bot_token=config.TELEGRAM_BOT_TOKEN, chat_id=config.TELEGRAM_CHAT_ID)
    await broadcaster.start()

    from src.core.event_bus import OrderEvent, SentinelKillEvent, RiskAlertEvent
    
    async def _broadcaster_handler(event):
        import html
        if isinstance(event, OrderEvent):
            if event.status == "FILLED" and event.direction in ["BUY", "SELL"]:
                symbol = html.escape(str(event.symbol))
                msg = f"ðŸŸ¢ <b>EXECUTION ENTRY</b>\nSymbol: {symbol}\nDirection: {event.direction}\nVolume: {event.volume}\nPrice: {event.price}\nConviction: {event.conviction:.2f}"
                await broadcaster.broadcast(msg)
            elif event.status == "REQUEST" and event.direction == "MODIFY_SL":
                # Using order modify SL as a proxy for break-even locks (as done in TickSentinel)
                # Note: telemetry.record_sentinel_event also tracks this as "DB_E_LOCK"
                symbol = html.escape(str(event.symbol))
                msg = f"ðŸ›¡ï¸ <b>DYNAMIC BREAK-EVEN LOCK</b>\nTicket: {event.ticket}\nSymbol: {symbol}\nNew SL: {event.price}"
                await broadcaster.broadcast(msg)
        elif isinstance(event, SentinelKillEvent):
            if event.reason == "MOMENTUM_EXHAUSTED":
                msg = "[EXHAUSTION KILL] Position closed preemptively due to momentum stall. Profit secured."
                await broadcaster.broadcast(msg)
        elif isinstance(event, RiskAlertEvent):
            safe_msg = html.escape(str(event.message))
            msg = f"âš ï¸ <b>RISK QUOTA / DRAWDOWN ALERT</b>\nLevel: {event.level}\nMessage: {safe_msg}"
            await broadcaster.broadcast(msg)

    event_bus.subscribe(OrderEvent, _broadcaster_handler)
    event_bus.subscribe(SentinelKillEvent, _broadcaster_handler)
    event_bus.subscribe(RiskAlertEvent, _broadcaster_handler)

    from src.core.event_bus import CommandEvent
    async def _command_handler(event: CommandEvent):
        if event.action == "RETRAIN_ORACLE":
            logger.warning("Main: Received RETRAIN_ORACLE command. Launching background retraining process.")
            try:
                import sys
                process = await asyncio.create_subprocess_exec(
                    sys.executable, "src/analytics/train_oracle.py",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                async def _wait_and_reload(p):
                    stdout, stderr = await p.communicate()
                    if p.returncode == 0:
                        logger.info("Main: Background retraining completed successfully. Triggering hot_reload.")
                        await oracle.hot_reload()
                    else:
                        logger.error(f"Main: Background retraining failed with code {p.returncode}\n{stderr.decode()}")
                
                asyncio.create_task(_wait_and_reload(process))
            except Exception as e:
                logger.error(f"Main: Failed to launch retrain process: {e}")
                
    event_bus.subscribe(CommandEvent, _command_handler)

    async def _drift_monitor_loop():
        tearsheet = TearsheetGenerator(event_bus)
        while True:
            await asyncio.sleep(3600)  # Check every hour
            try:
                await tearsheet.generate()
            except Exception as e:
                logger.error(f"Drift monitor error: {e}")

    # Core Engines
    bridge = MT5Bridge(event_bus, risk_manager=None, telemetry_logger=telemetry)
    await bridge.initialize()
    
    actual_balance = await bridge.get_live_balance()
    risk_manager = RiskManager(event_bus, live_balance=actual_balance)
    bridge.risk_manager = risk_manager
    
    # Background task tracking to prevent garbage collection
    bg_tasks = set()
    
    # Orphan Integration
    from src.alpha.order_flow_tracker import OrderFlowTracker
    from src.alpha.dynamic_calibrator import DynamicCalibrator, DynamicParamStore
    from src.data.macro_spies import MacroSpyNetwork
    
    order_flow = OrderFlowTracker(event_bus)
    
    calibrator_store = DynamicParamStore()
    dynamic_calibrator = DynamicCalibrator(calibrator_store)
    task_dc = asyncio.create_task(dynamic_calibrator.start())
    bg_tasks.add(task_dc)
    
    macro_spies = MacroSpyNetwork(event_bus)
    task_ms = asyncio.create_task(macro_spies.start())
    bg_tasks.add(task_ms)
    
    radar = RegimeRadar(event_bus=event_bus)
    oracle = MLOracle(event_bus)
    await oracle.load_model()
    
    scorer = AlphaScorer(
        radar=radar,
        oracle=oracle,
        event_bus=event_bus,
        calibrator_store=calibrator_store,
        order_flow_tracker=order_flow
    )
    
    sentinel = TickSentinel(event_bus, risk_manager, campaign_ledger, telemetry_logger=telemetry, alpha_scorer=scorer)
    
    from src.core.adaptive_tuner import AdaptiveTuner
    tuner = AdaptiveTuner(alpha_scorer=scorer, telemetry_state=None)
    telemetry.register_trade_closed_callback(tuner.on_trade_closed)
    tuner.start()

    
    orchestrator = AlphaHarvesterStrategy(
        event_bus=event_bus,
        risk_manager=risk_manager,
        execution_bridge=bridge,
        tick_sentinel=sentinel,
        alpha_scorer=scorer,
        campaign_ledger=campaign_ledger
    )
    
    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(shutdown(orchestrator, campaign_ledger, telemetry, broadcaster, tuner)))
        loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(shutdown(orchestrator, campaign_ledger, telemetry, broadcaster, tuner)))

    try:
        # Start engines
        task_eb = asyncio.create_task(event_bus.process_events())
        bg_tasks.add(task_eb)
        
        task_drift = asyncio.create_task(_drift_monitor_loop())
        bg_tasks.add(task_drift)
        await bridge.start_streams()
        task_s = asyncio.create_task(sentinel.start())
        bg_tasks.add(task_s)
        
        async def _delayed_browser_launch(url: str, delay: float = 1.5) -> None:
            await asyncio.sleep(delay)
            import os, sys, subprocess
            try:
                if sys.platform == 'win32':
                    os.startfile(url)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', url])
                else:
                    subprocess.Popen(['xdg-open', url])
                logger.info(f"Successfully triggered OS-level browser launch for {url}")
            except Exception as e:
                logger.warning(f"Failed to launch browser natively: {e}")

        logger.info("Auto-launching Telemetry Web HUD at http://localhost:8080 for Fund Manager...")
        asyncio.create_task(_delayed_browser_launch("http://localhost:8080"))

        # Start the continuous event-driven orchestrator
        await orchestrator.start()
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        logger.warning("KeyboardInterrupt caught in main async loop.")
    except Exception as e:
        logger.critical(f"Orchestrator crashed: {e}", exc_info=True)
    finally:
        await shutdown(orchestrator, campaign_ledger, telemetry, broadcaster, tuner)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received at entry point.")

