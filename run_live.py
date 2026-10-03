import sys
import os

if os.environ.get("AUREXIS_LAUNCHER") != "1":
    sys.exit("CRITICAL ERROR: Architectural Integrity Compromised. The system MUST be launched via start_aurexis.bat. Legacy shortcuts are strictly prohibited.")

import asyncio
import signal
import json
import logging
import MetaTrader5 as mt5

class LocalLaunchController:
    def __init__(self) -> None:
        self.shutdown_requested = False
        self.strategy = None
        self.bridge = None
        self.campaign_ledger = None
        self.telemetry_logger = None
        self.event_bus = None
        self.bus_task = None
        self.reconciler = None
        self.reconciler_task = None
        self.telemetry_server = None
        self.state_ledger = None
        
        self.telemetry_state = None

    async def initialize(self) -> None:
        # Import internally to eliminate global-scope instantiations blocking the boot
        from src.core.config_loader import load_environment_variables
        from src.core.logger import setup_async_logger
        from src.core.hud import TelemetryState
        from src.core.event_bus import EventBus
        from src.core.telemetry import TelemetryLogger
        from src.core.campaign_ledger import CampaignLedger
        from src.database.ledger import Ledger
        from src.alpha.dynamic_calibrator import DynamicParamStore
        from src.core.notifier import TelegramNotifier
        
        # TASK 1: Secure Environment Configuration
        load_environment_variables()
        setup_async_logger()
        
        self.telemetry_state = TelemetryState()
        
        # Instantiate Decoupled Architecture
        self.event_bus = EventBus()
        os.makedirs("logs", exist_ok=True)

        self.telegram_notifier = TelegramNotifier(self.event_bus)
        await self.telegram_notifier.start()
        
        self.telemetry_logger = TelemetryLogger("logs/local_telemetry.jsonl")
        await self.telemetry_logger.start()
        
        self.campaign_ledger = CampaignLedger(self.event_bus)
        await self.campaign_ledger.initialize()
        
        self.ledger = Ledger(self.event_bus)
        await self.ledger.initialize()

        self.dynamic_param_store = DynamicParamStore()
        
    async def run(self) -> None:
        await self.initialize()
        
        logger = logging.getLogger("LocalLaunchController")
        
        logger.info("Handing over execution to AlphaHarvester strategy loop...")
        
        # Pure asyncio execution
        self.bus_task = asyncio.create_task(self.event_bus.process_events())
        
        # Instantiate and initialize components in run()
        from src.core.telemetry_server import TelemetryServer
        from src.execution.bridge import MT5Bridge
        from src.execution.state_ledger import StateLedger

        self.telemetry_server = TelemetryServer(
            risk_manager=None,
            tick_sentinel=None,
            alpha_scorer=None,
            telemetry_state=self.telemetry_state,
            event_bus=self.event_bus
        )

        self.bridge = MT5Bridge(
            self.event_bus, 
            risk_manager=None, 
            calibrator_store=self.dynamic_param_store, 
            telemetry_logger=self.telemetry_logger,
            telemetry_state=self.telemetry_state
        )
        
        self.state_ledger = StateLedger()

        await self.telemetry_server.start()
        await self.state_ledger.sync()
        await self.bridge.initialize()
        
        # MT5 is initialized, now safe to reconcile campaign ledger
        await self.campaign_ledger.load_and_reconcile()
        self.campaign_ledger.start_realtime_reconciliation()
        
        from src.strategy.alpha_harvester import PreFlightDiagnostic, WarmupSequence
        import src.core.config as config
        
        # Trigger PreFlightDiagnostic explicitly after MT5 is initialized
        diagnostic_passed = await PreFlightDiagnostic.run(config.TRADING_SYMBOL)
        if not diagnostic_passed:
            raise RuntimeError("PreFlightDiagnostic failed.")
        
        actual_balance = await self.bridge.get_live_balance()
        if actual_balance <= 0.0:
            raise RuntimeError("Live balance is <= 0.0.")
            
        from src.execution.risk_manager import RiskManager
        risk_manager = RiskManager(self.event_bus, live_balance=actual_balance, telemetry_state=self.telemetry_state)
        self.bridge.risk_manager = risk_manager
        await self.bridge.start_streams()

        
        from src.core.alpha import RegimeRadar, MLOracle, AlphaScorer
        radar = RegimeRadar(self.event_bus)
        oracle = MLOracle(self.event_bus)
        await oracle.load_model()
        
        from src.alpha.order_flow_tracker import OrderFlowTracker
        order_flow = OrderFlowTracker(self.event_bus)
        
        alpha_scorer = AlphaScorer(radar, oracle, self.event_bus, self.dynamic_param_store, telemetry_state=self.telemetry_state, order_flow_tracker=order_flow)
        
        from src.core.adaptive_tuner import AdaptiveTuner
        self.tuner = AdaptiveTuner(alpha_scorer=alpha_scorer, telemetry_state=self.telemetry_state)
        self.telemetry_logger.register_trade_closed_callback(self.tuner.on_trade_closed)
        self.tuner.start()

        from src.execution.tick_sentinel import TickSentinel
        sentinel = TickSentinel(
            self.event_bus, 
            risk_manager, 
            self.campaign_ledger, 
            telemetry_logger=self.telemetry_logger,
            telemetry_state=self.telemetry_state,
            alpha_scorer=alpha_scorer,
            state_ledger=self.state_ledger
        )
        
        from src.core.reconciler import StateReconciler
        self.reconciler = StateReconciler(sentinel, risk_manager)
        if self.reconciler:
            self.reconciler_task = asyncio.create_task(self.reconciler.run_watchdog())

        # Trigger Warm-Up Sequence
        warmup_passed = await WarmupSequence.run(config.TRADING_SYMBOL, alpha_scorer)
        if not warmup_passed:
            raise RuntimeError("Historical Data warm-up failed.")
        
        from src.core.news_filter import NewsFilter
        self.news_filter = NewsFilter()
        await self.news_filter.start()
        
        from src.strategy.alpha_harvester import AlphaHarvesterStrategy
        from src.data.tick_vault import TickVault
        self.strategy = AlphaHarvesterStrategy(
            event_bus=self.event_bus,
            risk_manager=risk_manager,
            execution_bridge=self.bridge,
            tick_sentinel=sentinel,
            alpha_scorer=alpha_scorer,
            campaign_ledger=self.campaign_ledger,
            telemetry_state=self.telemetry_state,
            news_filter=self.news_filter,
            tick_vault=TickVault()
        )
        
        # Bind deferred Telemetry dependencies
        self.telemetry_server.risk_manager = self.strategy.risk_manager
        self.telemetry_server.tick_sentinel = self.strategy.tick_sentinel
        self.telemetry_server.alpha_scorer = self.strategy.alpha_scorer
        self.telemetry_server.strategy = self.strategy
                
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

        # Blocking wait - kept alive entirely by the native asyncio loop running AlphaHarvester
        await self.strategy.start()

    async def shutdown(self) -> None:
        logger = logging.getLogger("LocalLaunchController")
        if self.shutdown_requested:
            return
        logger.info("Initiating Graceful Shutdown Sequence...")
        self.shutdown_requested = True
            
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        
        if self.strategy:
            self.strategy.stop()
            
        if getattr(self, 'telemetry_server', None):
            try:
                original_loop = getattr(self.bus_task, 'get_loop', lambda: None)() if getattr(self, 'bus_task', None) else None
                if original_loop and not original_loop.is_closed():
                    await self.telemetry_server.stop()
                else:
                    logger.warning("Original event loop closed/missing. Bypassing telemetry_server.stop() to avoid AttributeError.")
            except AttributeError as e:
                logger.warning(f"Bypassing telemetry_server shutdown due to event loop destruction: {e}")
            except Exception as e:
                logger.warning(f"Error during telemetry_server shutdown: {e}")
            
        if self.reconciler:
            self.reconciler._running = False
            
        if getattr(self, 'tuner', None):
            self.tuner.stop()

        if getattr(self, 'news_filter', None):
            self.news_filter.stop()

        if getattr(self, 'telegram_notifier', None):
            await self.telegram_notifier.stop()
            
        if self.event_bus:
            self.event_bus.stop()
            if self.bus_task and current_loop and getattr(self.bus_task, 'get_loop', lambda: None)() is current_loop:
                try:
                    await self.bus_task
                except asyncio.CancelledError:
                    pass
        
        if self.campaign_ledger:
            logger.info("Flushing Campaign Ledger (SQLite)...")
            try:
                await self.campaign_ledger.perform_weekend_maintenance()
            except Exception as e:
                logger.error(f"Failed to flush Campaign Ledger: {e}")
            
        if self.telemetry_logger:
            logger.info("Flushing remaining telemetry logs to disk...")
            while not self.telemetry_logger._queue.empty():
                try:
                    item = self.telemetry_logger._queue.get_nowait()
                    with open(self.telemetry_logger.log_path, 'a') as f:
                        f.write(json.dumps(item) + '\n')
                except asyncio.QueueEmpty:
                    break
            
            if self.telemetry_logger._worker_task and current_loop and getattr(self.telemetry_logger._worker_task, 'get_loop', lambda: None)() is current_loop:
                try:
                    await self.telemetry_logger.stop()
                except Exception:
                    pass
            else:
                self.telemetry_logger._running = False
            
        logger.info("Closing MT5 terminal connection...")
        try:
            mt5.shutdown()
        except Exception:
            pass
        logger.info("Graceful Shutdown Complete.")

def main() -> None:
    controller = LocalLaunchController()
    
    async def _runner() -> None:
        loop = asyncio.get_running_loop()
        
        def shutdown_handler() -> None:
            if not controller.shutdown_requested:
                logging.getLogger("LocalLaunchController").info("Shutdown signal received (SIGTERM/SIGINT).")
                asyncio.create_task(controller.shutdown())
                
        if sys.platform != 'win32':
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, shutdown_handler)
                
        try:
            await controller.run()
        except asyncio.CancelledError:
            pass
            
    try:
        asyncio.run(_runner())
    except KeyboardInterrupt:
        logging.getLogger("LocalLaunchController").info("KeyboardInterrupt received (Ctrl+C). Initiating emergency graceful shutdown...")
        if not controller.shutdown_requested:
            asyncio.run(controller.shutdown())
    except BaseException as e:
        if type(e).__name__ == "ConfigError":
            logging.getLogger("LocalLaunchController").error(f"Configuration Error: {e}")
        else:
            logging.getLogger("LocalLaunchController").error(f"Execution halted: {e}", exc_info=True)
    finally:
        if not controller.shutdown_requested:
            asyncio.run(controller.shutdown())

if __name__ == "__main__":
    main()
