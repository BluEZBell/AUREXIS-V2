import asyncio
import logging
from typing import Any, Deque, Optional
from collections import deque
import numpy as np

from src.core.event_bus import TickEvent

logger = logging.getLogger("order_flow_tracker")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class OrderFlowState:
    def __init__(self) -> None:
        self.cumulative_delta: float = 0.0
        self.delta_momentum: float = 0.0

class OrderFlowTracker:
    def __init__(self, event_bus: Any, window_size: int = 100) -> None:
        self.event_bus = event_bus
        self.window_size: int = window_size
        self.state: OrderFlowState = OrderFlowState()
        
        self._last_ask: Optional[float] = None
        self._last_bid: Optional[float] = None
        
        self._delta_window: Deque[float] = deque(maxlen=window_size)
        
        self._tick_queue: asyncio.Queue = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        
        # Subscribe to TickEvent
        self.event_bus.subscribe(TickEvent, self._enqueue_tick)
        
        # Start background task if event loop is running, else it needs to be started
        try:
            self._task = asyncio.create_task(self._process_ticks())
        except RuntimeError:
            pass # No running event loop
            
    async def _enqueue_tick(self, event: TickEvent) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._process_ticks())
        await self._tick_queue.put(event)
        
    async def _process_ticks(self) -> None:
        while True:
            try:
                event = await self._tick_queue.get()
                
                tick_delta: float = 0.0
                
                if self._last_ask is not None and self._last_bid is not None:
                    # Get tick volume or default to 1.0 for standard ticks
                    vol = event.volume if event.volume > 0 else 1.0
                    
                    is_buy_flag = False
                    is_sell_flag = False
                    
                    if hasattr(event, 'flags') and event.flags > 0:
                        # MT5 TICK_FLAG_BUY = 32, TICK_FLAG_SELL = 64
                        is_buy_flag = (event.flags & 32) == 32
                        is_sell_flag = (event.flags & 64) == 64
                        
                    if is_buy_flag:
                        tick_delta = vol
                    elif is_sell_flag:
                        tick_delta = -vol
                    else:
                        # Fallback to Price Action Micro-Momentum
                        mid_price = (event.ask + event.bid) / 2.0
                        last_mid = (self._last_ask + self._last_bid) / 2.0
                        price_delta = mid_price - last_mid
                        
                        if price_delta > 0.000001:
                            tick_delta = vol
                        elif price_delta < -0.000001:
                            tick_delta = -vol
                        
                self._last_ask = event.ask
                self._last_bid = event.bid
                
                # Rolling Accumulation (Non-blocking moving sum)
                self._delta_window.append(tick_delta)
                
                if len(self._delta_window) > 0:
                    deltas = np.array(self._delta_window, dtype=float)
                    self.state.cumulative_delta = float(np.sum(deltas))
                    
                    momentum_period = min(20, len(deltas))
                    if momentum_period > 0:
                        self.state.delta_momentum = float(np.sum(deltas[-momentum_period:]))
                    else:
                        self.state.delta_momentum = 0.0
                else:
                    self.state.cumulative_delta = 0.0
                    self.state.delta_momentum = 0.0
                    
                self._tick_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"OrderFlowTracker error: {e}")

    def get_state(self) -> OrderFlowState:
        return self.state
