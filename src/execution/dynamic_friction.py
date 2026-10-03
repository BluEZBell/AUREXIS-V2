import asyncio
import collections
from typing import Deque
from src.core.event_bus import EventBus, OrderEvent, RiskAlertEvent
from src.core.config import setup_logger, run_mt5_task
import MetaTrader5 as mt5

logger = setup_logger("dynamic_friction")

class DynamicFrictionEngine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.slippage_history: Deque[float] = collections.deque(maxlen=5)
        self.toxic_threshold: float = 15.0
        self._point_cache: dict[str, float] = {}
        self._running_sum: float = 0.0
        
        self.event_bus.subscribe(OrderEvent, self._handle_order_event)

    async def _get_point(self, symbol: str) -> float:
        if symbol not in self._point_cache:
            sym_info = await run_mt5_task(lambda: mt5.symbol_info(symbol))
            if sym_info:
                self._point_cache[symbol] = sym_info.point
        return self._point_cache.get(symbol, 0.0)

    async def _handle_order_event(self, event: OrderEvent) -> None:
        if event.status != "FILLED" or event.requested_price <= 0.0:
            return
            
        point = await self._get_point(event.symbol)
        
        # Calculate slippage in points
        price_diff = abs(event.requested_price - event.price)
        slippage_points = price_diff / point if point > 0 else 0.0
        
        if len(self.slippage_history) == 5:
            self._running_sum -= self.slippage_history[0]
            
        self.slippage_history.append(slippage_points)
        self._running_sum += slippage_points
        
        avg_slippage = self.get_dynamic_offset()
        
        if avg_slippage > self.toxic_threshold:
            alert = RiskAlertEvent(
                level="WARNING",
                message=f"TOXIC BROKER SLIPPAGE DETECTED: Avg {avg_slippage:.2f} pts"
            )
            await self.event_bus.publish(alert)

    def get_dynamic_offset(self) -> float:
        if not self.slippage_history:
            return 0.0
        return self._running_sum / len(self.slippage_history)
