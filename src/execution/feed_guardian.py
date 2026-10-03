import asyncio
import time
import MetaTrader5 as mt5

from src.core.config import setup_logger, run_mt5_task
from src.core.event_bus import EventBus, TickEvent, FeedFreezeEvent, RiskAlertEvent
import src.core.config as config

logger = setup_logger("feed_guardian")

class FeedGuardian:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._running = False
        self._last_tick_time = time.time()
        self._current_spread = 0.0
        self._is_frozen = False
        self._point_value_cache = {}
        
        self.max_latency_sec = getattr(config, 'FEED_MAX_LATENCY_SEC', 10.0)
        self.max_spread_points = getattr(config, 'FEED_MAX_SPREAD_POINTS', 40.0)

        self.event_bus.subscribe(TickEvent, self._handle_tick)

    async def start(self):
        self._running = True
        self._last_tick_time = time.time()
        asyncio.create_task(self._monitor_loop())
        logger.info(f"FeedGuardian Started. Max Latency: {self.max_latency_sec}s, Max Spread: {self.max_spread_points} pts.")

    def stop(self):
        self._running = False
        logger.info("FeedGuardian Stopped.")

    async def _get_point(self, symbol: str) -> float:
        if symbol in self._point_value_cache:
            return self._point_value_cache[symbol]
        
        try:
            symbol_info = await run_mt5_task(lambda: mt5.symbol_info(symbol))
            if symbol_info:
                self._point_value_cache[symbol] = symbol_info.point
                return symbol_info.point
        except Exception:
            pass
        return 0.01

    async def _handle_tick(self, event: TickEvent):
        self._last_tick_time = time.time()
        point = await self._get_point(event.symbol)
        if point > 0:
            self._current_spread = (event.ask - event.bid) / point

    async def _monitor_loop(self):
        while self._running:
            try:
                await asyncio.sleep(1.0)
                
                time_since_last = time.time() - self._last_tick_time
                freeze_reason = None
                
                if time_since_last > self.max_latency_sec:
                    freeze_reason = f"STALE FEED (Latency: {time_since_last:.1f}s)"
                elif self._current_spread > self.max_spread_points:
                    freeze_reason = f"TOXIC LIQUIDITY (Spread: {self._current_spread:.1f} pts)"

                if freeze_reason:
                    if not self._is_frozen:
                        logger.warning(f"FeedGuardian: {freeze_reason}. (FREEZES DISABLED - Continuing Operation)")
                        # NO FeedFreezeEvent(is_frozen=True) published
                        await self.event_bus.publish(RiskAlertEvent(level="WARNING", message=f"FEED ALERT: {freeze_reason} (Adaptive mode)"))
                else:
                    if self._is_frozen:
                        # Ensure we don't lift it prematurely if it was just 1 tick of normal spread
                        self._is_frozen = False
                        logger.info("FeedGuardian: Conditions normalized.")
                        await self.event_bus.publish(RiskAlertEvent(level="INFO", message="FEED GUARDIAN: Conditions normalized."))
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"FeedGuardian Error: {e}")
