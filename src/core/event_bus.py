import asyncio
from dataclasses import dataclass
from typing import Callable, Dict, List, Any, Awaitable
from src.core.config import setup_logger

logger = setup_logger("event_bus")

@dataclass
class TickEvent:
    symbol: str
    bid: float
    ask: float
    time: int
    volume: float = 1.0
    flags: int = 0

@dataclass
class StructuralTrendEvent:
    symbol: str
    m15_trend: str # "BULLISH", "BEARISH", "NEUTRAL"
    h1_trend: str  # "BULLISH", "BEARISH", "NEUTRAL"
    m15_close: float
    time: int
    m15_distance: float = 0.0 # [Y-Axis Depth] Distance from M15 SMA in points
    h1_distance: float = 0.0  # [Y-Axis Depth] Distance from H1 SMA in points
    m15_distance_z_score: float = 0.0 # Distance in ATRs
    m15_atr: float = 0.0 # Phase 9: Added ATR for data lake
    m15_rsi: float = 50.0
    m15_adx: float = 25.0
    m15_bullish_candle: bool = True
    m15_bearish_candle: bool = True
    hyper_conservative: bool = False
    poc: float = 0.0
@dataclass
class SignalEvent:
    symbol: str
    direction: str # "BUY", "SELL", or "NEUTRAL"
    strategy_id: str
    price: float
    conviction: float = 0.0
    volume: float = 0.01
    loss_streak: int = 0
    cycle_id: int = 0
    order_type: str = "PROBE" # "PROBE" or "SET"
    regime: str = "UNKNOWN"
    mtf_volume_confirmed: bool = False
    is_hyper_scale: bool = False
    generation_time: float = 0.0
    soft_sl: float = 0.0
    soft_tp: float = 0.0
    atr: float = 0.0

@dataclass
class MacroUpdateEvent:
    dxy: float
    us10y: float
    usdjpy: float
    vix: float
    xagusd: float
    usdcnh: float
    usoil: float
    eurusd_val: float = 0.0
    us500_val: float = 0.0
    is_historical: bool = False
    timestamp: float = 0.0

@dataclass
class OrderEvent:
    ticket: int
    symbol: str
    direction: str
    volume: float
    price: float
    status: str # "FILLED", "REJECTED"
    cycle_id: int = 0
    order_type: str = "PROBE" # "PROBE" or "SET"
    requested_price: float = 0.0
    conviction: float = 0.0
    regime: str = "UNKNOWN"
    soft_sl: float = 0.0
    soft_tp: float = 0.0

@dataclass
class TargetHitEvent:
    cycle_id: int

@dataclass
class SentinelKillEvent:
    ticket: int
    cycle_id: int
    reason: str
    pnl: float

@dataclass
class ScoutSuccessEvent:
    cycle_id: int
    ticket: int
    pnl: float

@dataclass
class ScoutFailEvent:
    cycle_id: int
    ticket: int
    pnl: float

@dataclass
class SpikeDetectedEvent:
    cycle_id: int
    price_diff: float

@dataclass
class PositionsUpdateEvent:
    positions: list
    balance: float = 0.0
    equity: float = 0.0
    free_margin: float = 0.0
    margin_level: float = 0.0
    login: int = 0
    account_name: str = "N/A"
    server: str = "N/A"

@dataclass
class ErrorEvent:
    source: str
    message: str
    critical: bool = False

@dataclass
class CommandEvent:
    action: str
    payload: Any = None

@dataclass
class StrategyStateEvent:
    strategy_id: str
    cycle_state: str
    swarm_type: str
    scout_dir: str = "NONE"
    whipsaw_locked: bool = False
    whipsaw_locked_until: float = 0.0
    current_score: float = 0.0
    adx_m15: float = 0.0
    z_score: float = 0.0
    atr_m15: float = 0.0

@dataclass
class LogEvent:
    message: str

@dataclass
class RiskAlertEvent:
    level: str
    message: str

@dataclass
class MilestoneEvent:
    milestone_name: str
    message: str

@dataclass
class OracleVetoEvent:
    symbol: str
    direction: str
    win_probability: float
    reason: str = "Low Probability"

@dataclass
class FeedFreezeEvent:
    is_frozen: bool
    reason: str

@dataclass
class NewsBlackoutEvent:
    active: bool
    event_name: str
    minutes_to_event: float

@dataclass
class WeekendBlackoutEvent:
    active: bool

class EventBus:
    def __init__(self):
        self._subscribers: Dict[type, List[Callable[[Any], Awaitable[None]]]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
    
    def subscribe(self, event_type: type, callback: Callable[[Any], Awaitable[None]]):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.info(f"Subscribed {callback.__name__} to {event_type.__name__}")
        
    async def publish(self, event: Any):
        await self._queue.put(event)
        
    async def process_events(self):
        self._running = True
        logger.info("Event Bus processing started.")
        while self._running:
            try:
                event = await self._queue.get()
                if event is None:
                    self._queue.task_done()
                    continue
                event_type = type(event)
                
                if event_type in self._subscribers:
                    for callback in self._subscribers[event_type]:
                        def _handle_task_result(t: asyncio.Task, cb_name=callback.__name__):
                            try:
                                exc = t.exception()
                                if exc:
                                    import traceback
                                    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                                    logger.error(f"Error in subscriber {cb_name} for {event_type.__name__}:\n{tb_str}")
                            except asyncio.CancelledError:
                                pass
                        
                        task = asyncio.create_task(callback(event))
                        task.add_done_callback(_handle_task_result)
                self._queue.task_done()
            except asyncio.CancelledError:
                self._running = False
                logger.info("Event Bus processing stopped.")
                break
            except Exception as e:
                logger.error(f"Event Bus error: {e}")
                
    def stop(self):
        self._running = False
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass
