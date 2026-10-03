import asyncio
from src.core.config import setup_logger, run_mt5_task
from src.core.event_bus import EventBus, OrderEvent, RiskAlertEvent
import src.core.config as config
import MetaTrader5 as mt5

logger = setup_logger("execution_monitor")

class ExecutionMonitor:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.max_slippage_points = getattr(config, 'MAX_SLIPPAGE_POINTS', 30.0)
        self.consecutive_slippage_hits = 0
        self.consecutive_limit = 3
        self._point_value_cache = {}
        
        self.event_bus.subscribe(OrderEvent, self._handle_order)

    async def start(self):
        logger.info(f"ExecutionMonitor Started. Max Allowed Slippage: {self.max_slippage_points} pts.")
        
    def stop(self):
        logger.info("ExecutionMonitor Stopped.")

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

    async def _handle_order(self, event: OrderEvent):
        # We only calculate slippage for filled orders with a valid requested price
        if event.status != "FILLED" or event.requested_price <= 0:
            return
            
        point = await self._get_point(event.symbol)
        if point <= 0:
            return

        # Calculate exact absolute slippage in points
        slippage_points = abs(event.price - event.requested_price) / point

        if slippage_points > self.max_slippage_points:
            self.consecutive_slippage_hits += 1
            logger.critical(f"MASSIVE SLIPPAGE DETECTED: {slippage_points:.1f} pts! "
                            f"(Requested: {event.requested_price:.2f}, Filled: {event.price:.2f}, "
                            f"Hit: {self.consecutive_slippage_hits}/{self.consecutive_limit})")
                            
            if self.consecutive_slippage_hits >= self.consecutive_limit:
                msg = f"TOXIC EXECUTION WARNING: Experienced >{self.max_slippage_points} pts slippage {self.consecutive_limit} times consecutively! Broker execution may be compromised."
                logger.critical(msg)
                await self.event_bus.publish(RiskAlertEvent(level="CRITICAL", message=msg))
                # Reset after firing to avoid spamming alerts for every subsequent tick
                self.consecutive_slippage_hits = 0
        else:
            if self.consecutive_slippage_hits > 0:
                logger.info(f"Execution Normalized. Slippage: {slippage_points:.1f} pts. Resetting counter.")
                self.consecutive_slippage_hits = 0
