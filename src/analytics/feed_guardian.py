import time
import asyncio
import logging
import MetaTrader5 as mt5
from src.core.event_bus import EventBus, TickEvent, CommandEvent, ErrorEvent
from src.core.config import setup_logger, run_mt5_task

logger = setup_logger("feed_guardian")

class FeedGuardian:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.event_bus.subscribe(TickEvent, self.handle_tick)
        
        self._last_tick_time: float = time.time()
        self._is_frozen: bool = False
        self._stable_count: int = 0
        self._running: bool = False
        self._watchdog_task: asyncio.Task | None = None

        logger.info("Feed Freeze & Latency Guardian initialized.")

    async def handle_tick(self, event: TickEvent) -> None:
        self._last_tick_time = time.time()

    async def start(self) -> None:
        self._running = True
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())
        logger.info("Feed Guardian Watchdog started.")

    async def stop(self) -> None:
        self._running = False
        if self._watchdog_task:
            self._watchdog_task.cancel()
            
    async def _get_ping(self) -> float:
        # Returns ping in microseconds
        def _fetch_terminal():
            info = mt5.terminal_info()
            if info is None:
                return 0.0
            return info.ping_last
        return await run_mt5_task(_fetch_terminal)

    async def _watchdog_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(1.0)
                
                current_time = time.time()
                tick_delta = current_time - self._last_tick_time
                ping_mu = await self._get_ping()
                
                # Check for Feed Degradation
                feed_stale = tick_delta > 5.0
                latency_spike = ping_mu > 250000.0  # 250ms
                
                if feed_stale or latency_spike:
                    self._stable_count = 0
                    
                    if not self._is_frozen:
                        self._is_frozen = True
                        reason = "FEED FREEZE" if feed_stale else "LATENCY SPIKE"
                        msg = f"{reason} DETECTED (Delta: {tick_delta:.1f}s, Ping: {ping_mu / 1000.0:.1f}ms). HALTING ENTRIES."
                        logger.warning(msg)
                        
                        await self.event_bus.publish(ErrorEvent(source="FeedGuardian", message=msg, critical=False))
                
                else:
                    # Check for Recovery (tick < 1.0s and ping < 200ms)
                    if self._is_frozen and tick_delta < 1.0 and (ping_mu > 0 and ping_mu < 200000.0):
                        self._stable_count += 1
                        if self._stable_count >= 3:
                            self._is_frozen = False
                            self._stable_count = 0
                            logger.info("Network conditions stabilized. Feed freeze/latency warnings cleared.")
                            # Note: The system will automatically resume when structural momentum returns,
                            # but we clear the local frozen state here to allow future alerts.
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in FeedGuardian watchdog loop: {e}")
