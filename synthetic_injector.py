import asyncio
import logging
import random
import time
from typing import Optional

from src.core.event_bus import (
    EventBus, 
    TickEvent, 
    PositionsUpdateEvent, 
    MilestoneEvent, 
    ErrorEvent,
    RiskAlertEvent,
    CommandEvent
)

logger = logging.getLogger("synthetic_injector")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class SyntheticInjector:
    def __init__(self, event_bus: EventBus, risk_manager=None):
        self.event_bus = event_bus
        self.risk_manager = risk_manager
        self._running = False

    async def inject_ticks(self) -> None:
        """
        TASK 1: High-Frequency Tick Injection
        Rapidly injects simulated TickEvents for XAUUSD at 100 ticks/sec.
        Prices violently fluctuate to mimic high-impact news event.
        """
        logger.info("Starting High-Frequency Tick Injection (100 ticks/sec)...")
        base_bid = 2000.0
        while self._running:
            bid = base_bid + random.uniform(-15.0, 15.0)
            ask = bid + random.uniform(0.1, 2.5)
            
            tick = TickEvent(
                symbol="XAUUSD",
                bid=bid,
                ask=ask,
                time=int(time.time() * 1000),
                volume=random.uniform(1.0, 50.0)
            )
            await self.event_bus.publish(tick)
            
            # 100 ticks per second -> 0.01s sleep
            await asyncio.sleep(0.01)

    async def inject_doomsday(self) -> None:
        """
        TASK 2: Doomsday Risk Stress Test
        Inject simulated PositionsUpdateEvents reporting a 99% drawdown.
        """
        logger.info("Starting Doomsday Risk Stress Test (99% Drawdown)...")
        while self._running:
            doom_event = PositionsUpdateEvent(
                positions=[],
                balance=100000.0,
                equity=1000.0,  # 99% Drawdown
                free_margin=1000.0,
                margin_level=1.0,
                login=999999,
                account_name="DOOMSDAY_FUND",
                server="SYNTHETIC_BROKER"
            )
            await self.event_bus.publish(doom_event)
            
            if self.risk_manager:
                # Actually trigger the latch logic
                await self.risk_manager.check_drawdown_limits(1000.0, 100000.0)
                
            # Inject periodically without blocking
            await asyncio.sleep(1.0)

    async def inject_eod_telemetry(self) -> None:
        """
        TASK 3: EOD Modal & Telemetry Trigger
        Inject mock MilestoneEvent and Error/Warning events.
        """
        logger.info("Injecting EOD Modal & Telemetry Trigger...")
        
        # Fire a command event for telemetry broadcaster
        await self.event_bus.publish(CommandEvent(
            action="100_PCT_ROI_VAULT_SECURED",
            payload=None
        ))
        
        # Also fire a general MilestoneEvent for the web UI/logs
        await self.event_bus.publish(MilestoneEvent(
            milestone_name="100_PCT_ROI_VAULT_SECURED",
            message="Synthetic EOD Trigger: 100% Vault Secured"
        ))
        
        # Fire mock Warning to trigger TelemetryBroadcaster risk alert webhook
        await self.event_bus.publish(RiskAlertEvent(
            level="WARNING",
            message="SYNTHETIC STRESS: Extreme volatility detected."
        ))
        
        # Fire mock ErrorEvent to verify it doesn't halt the event loop if non-critical
        await self.event_bus.publish(ErrorEvent(
            source="SyntheticStressTest",
            message="Simulated non-critical telemetry error.",
            critical=False
        ))

    async def run(self, duration: int = 30) -> None:
        """
        Main runner for the stress test.
        Runs for `duration` seconds, then gracefully shuts down.
        """
        logger.info(f"Starting Institutional Synthetic Stress Tester for {duration} seconds...")
        self._running = True
        
        tick_task = asyncio.create_task(self.inject_ticks())
        doom_task = asyncio.create_task(self.inject_doomsday())
        
        # At halfway point, inject EOD Telemetry
        await asyncio.sleep(duration / 2.0)
        await self.inject_eod_telemetry()
        
        # Wait for the remainder of the duration
        await asyncio.sleep(duration / 2.0)
        
        self._running = False
        await asyncio.gather(tick_task, doom_task, return_exceptions=True)
        logger.info("STRESS TEST COMPLETE")

async def run_standalone() -> None:
    """
    Instantiates a mock publisher (EventBus) if running standalone,
    along with Web Dashboard and Telemetry components for visual verification.
    """
    logger.info("Running in Standalone Mock Publisher Mode")
    
    event_bus = EventBus()
    bus_task = asyncio.create_task(event_bus.process_events())
    
    # Attempt to initialize components so they subscribe to the standalone EventBus
    rm = None
    tb = None
    server = None
    web_task = None
    
    try:
        from src.execution.risk_manager import RiskManager
        from src.core.telemetry_broadcaster import TelemetryBroadcaster
        from src.web.web_dashboard import app, inject_event_bus
        from src.core.config import TELEMETRY_WEBHOOK_URL, WEB_PORT
        import uvicorn
        
        rm = RiskManager(event_bus, live_balance=1000.0)
        
        tb = TelemetryBroadcaster(event_bus, TELEMETRY_WEBHOOK_URL)
        await tb.start()
        
        inject_event_bus(event_bus)
        
        # We start the web dashboard on a different port to avoid conflicts
        # if main.py is simultaneously running in another console.
        mock_port = WEB_PORT + 1
        config_uv = uvicorn.Config(app=app, host="127.0.0.1", port=mock_port, log_level="warning")
        server = uvicorn.Server(config_uv)
        web_task = asyncio.create_task(server.serve())
        
        logger.info(f"Mock Web Dashboard started on http://127.0.0.1:{mock_port}")
    except ImportError as e:
        logger.warning(f"Could not load some core components for standalone mode: {e}")

    injector = SyntheticInjector(event_bus, rm)
    await injector.run(30)
    
    # Teardown
    event_bus.stop()
    await bus_task
    
    if tb:
        await tb.stop()
    if server and web_task:
        server.should_exit = True
        await web_task

if __name__ == "__main__":
    try:
        asyncio.run(run_standalone())
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Shutting down.")
