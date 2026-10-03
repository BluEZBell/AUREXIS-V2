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
                    # Aggressive Buying (price ticks up)
                    if event.ask > self._last_ask or event.bid > self._last_bid:
                        tick_delta = event.volume
                    # Aggressive Selling (price ticks down)
                    elif event.ask < self._last_ask or event.bid < self._last_bid:
                        tick_delta = -event.volume
                        
                self._last_ask = event.ask
                self._last_bid = event.bid
                
                self._delta_window.append(tick_delta)
                
                # Vectorized operations
                deltas = np.array(self._delta_window, dtype=float)
                self.state.cumulative_delta = float(np.sum(deltas))
                
                momentum_period = min(10, len(deltas))
                if momentum_period > 0:
                    self.state.delta_momentum = float(np.sum(deltas[-momentum_period:]))
                else:
                    self.state.delta_momentum = 0.0
                    
                self._tick_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"OrderFlowTracker error: {e}")

    def get_state(self) -> OrderFlowState:
        return self.state
