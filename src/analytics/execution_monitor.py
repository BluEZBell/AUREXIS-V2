import logging
from src.core.event_bus import EventBus, OrderEvent, ErrorEvent
from src.core.config import setup_logger
import src.core.config as config
import MetaTrader5 as mt5

logger = setup_logger("execution_monitor")

class ExecutionMonitor:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.event_bus.subscribe(OrderEvent, self.handle_order)
        logger.info("Execution Integrity Monitor initialized.")
        self._point = None

    async def _get_point(self):
        if self._point is not None:
            return self._point
        
        # Async-safe MT5 access logic if needed, but for point we can just fetch it securely or rely on standard point size
        from src.core.config import run_mt5_task
        point_info = await run_mt5_task(lambda: mt5.symbol_info(config.TRADING_SYMBOL))
        if point_info:
            self._point = point_info.point
        else:
            self._point = 0.01 if "JPY" in config.TRADING_SYMBOL else 0.00001
        return self._point

    async def handle_order(self, event: OrderEvent):
        # We only monitor entry orders (PROBE/SET) that have a requested price
        if event.status == "FILLED" and event.direction in ["BUY", "SELL"] and event.requested_price > 0.0:
            point = await self._get_point()
            if point <= 0.0:
                return

            if event.direction == "BUY":
                # Slippage for BUY: Actual price is HIGHER than requested price
                slippage_raw = event.price - event.requested_price
            else:
                # Slippage for SELL: Actual price is LOWER than requested price
                slippage_raw = event.requested_price - event.price

            slippage_points = slippage_raw / point
            
            # Log all execution metrics (even positive/negative slippage)
            logger.info(f"[EXECUTION] Ticket {event.ticket} ({event.order_type} {event.direction}) | Requested: {event.requested_price:.5f} | Filled: {event.price:.5f} | Slippage: {slippage_points:.1f} pts")

            from src.core.config import run_mt5_task
            def _get_spread():
                ti = mt5.symbol_info_tick(config.TRADING_SYMBOL)
                si = mt5.symbol_info(config.TRADING_SYMBOL)
                if ti and si and si.point > 0:
                    return (ti.ask - ti.bid) / si.point
                return 0.0
            current_spread = await run_mt5_task(_get_spread)

            # Warning Threshold
            if slippage_points > current_spread * 1.5:
                logger.warning(f"⚠️ HIGH SLIPPAGE DETECTED: {slippage_points:.1f} points on Ticket {event.ticket}. Market liquidity may be degrading.")

            # Critical Alert Threshold (Telegram)
            if slippage_points > current_spread * 3.0:
                msg = f"CRITICAL EXECUTION SLIPPAGE: {slippage_points:.1f} points on {event.direction} {config.TRADING_SYMBOL}. Check broker manipulation or news spikes!"
                logger.error(msg)
                await self.event_bus.publish(ErrorEvent(source="ExecutionMonitor", message=msg, critical=False))
