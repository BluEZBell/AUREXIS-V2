import logging
import MetaTrader5 as mt5
from src.core.event_bus import EventBus, OrderEvent, RiskAlertEvent, StrategyStateEvent
from src.core.config import setup_logger, run_mt5_task

logger = setup_logger("execution_auditor")

class ExecutionAuditor:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.event_bus.subscribe(OrderEvent, self.handle_order)
        self.event_bus.subscribe(StrategyStateEvent, self.handle_strategy_state)
        
        self._current_atr_m15 = 0.0
        self._point_cache = {}
        
        self.total_orders = 0
        self.filled_orders = 0

    async def start(self):
        logger.info("Execution Integrity & Telemetry Auditor initialized and listening.")

    def stop(self):
        logger.info("ExecutionAuditor Stopped.")

    async def handle_strategy_state(self, event: StrategyStateEvent):
        if hasattr(event, 'atr_m15'):
            self._current_atr_m15 = event.atr_m15

    async def _get_point(self, symbol: str):
        if symbol in self._point_cache:
            return self._point_cache[symbol]
        
        def _fetch_point():
            sym_info = mt5.symbol_info(symbol)
            if sym_info:
                return sym_info.point
            return None
            
        point = await run_mt5_task(_fetch_point)
        if point:
            self._point_cache[symbol] = point
            return point
            
        return 0.00001 # fallback

    async def handle_order(self, event: OrderEvent):
        if event.status == "REQUEST":
            self.total_orders += 1
            
        if event.status == "FILLED":
            self.filled_orders += 1
            
        fill_rate = (self.filled_orders / self.total_orders) * 100.0 if self.total_orders > 0 else 0.0
        
        if event.status == "FILLED" and event.requested_price > 0:
            point = await self._get_point(event.symbol)
            
            # Slippage: The absolute point difference between requested_price and actual price
            slippage_raw = abs(event.requested_price - event.price)
            slippage_points = slippage_raw / point if point > 0 else 0.0
            
            atr_points = self._current_atr_m15 / point if point > 0 else 0.0
            
            logger.info(f"[EXECUTION AUDITOR] Ticket {event.ticket} | Slippage: {slippage_points:.1f} pts | ATR: {atr_points:.1f} pts | Fill Rate: {fill_rate:.1f}%")
            
            massive_gap_threshold = 500.0
            
            # Calculate threshold if ATR is available, else rely on massive gap threshold
            atr_threshold = 1.5 * atr_points if atr_points > 0.0 else float('inf')
            
            if slippage_points > atr_threshold or slippage_points > massive_gap_threshold:
                alert_msg = (f"[TOXIC_EXECUTION_SLIPPAGE] detected on {event.symbol} (Ticket: {event.ticket}). "
                             f"Slippage: {slippage_points:.1f} pts > Threshold")
                logger.warning(alert_msg)
                await self.event_bus.publish(RiskAlertEvent(level="WARNING", message=alert_msg))
