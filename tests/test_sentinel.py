import pytest
import asyncio
import time
from unittest.mock import MagicMock
from collections import namedtuple
from src.core.event_bus import EventBus, TickEvent, StructuralTrendEvent, OrderEvent
from src.core.campaign_ledger import CampaignLedger, CampaignCycle
from src.execution.tick_sentinel import TickSentinel
import src.core.config as config

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_sentinel.db")

@pytest.mark.asyncio
async def disabled_test_time_decay_kill(db_path, mock_mt5_api):
    bus = EventBus()
    ledger = CampaignLedger(bus)
    ledger.db_path = db_path
    await ledger.initialize()
    
    sentinel = TickSentinel(bus, None, ledger)
    await sentinel.start()
    
    cycle = await ledger.start_cycle(100, "BUY")
    cycle.state = "SCOUT_ACTIVE"
    cycle.probe_ticket = 555
    cycle.cycle_pnl = 0.5 # Stagnant < 1.0 (spread_cost * 2)
    await ledger.save_cycle(cycle)
    
    # Mock MT5 position older than 45 mins (2700s)
    MockPos = namedtuple('MockPos', ['ticket', 'price_open', 'time', 'sl', 'volume'])
    mock_mt5_api.positions_get.return_value = (
        MockPos(ticket=555, price_open=1900.0, time=time.time() - 3000, sl=0.0, volume=0.01), # 3000 seconds ago
    )
    MockTick = namedtuple('MockTick', ['bid', 'ask'])
    mock_mt5_api.symbol_info_tick.return_value = MockTick(bid=1900.0, ask=1900.5)
    
    MockSymbol = namedtuple('MockSymbol', ['point', 'trade_stops_level', 'swap_long', 'swap_short', 'swap_mode', 'spread', 'trade_tick_size', 'trade_tick_value'])
    mock_mt5_api.symbol_info.return_value = MockSymbol(point=0.01, trade_stops_level=10, swap_long=-1.0, swap_short=-1.0, swap_mode=0, spread=20, trade_tick_size=0.01, trade_tick_value=1.0)
    closed_events = []
    async def capture_close(event: OrderEvent):
        closed_events.append(event)
    bus.subscribe(OrderEvent, capture_close)
    
    bus_task = asyncio.create_task(bus.process_events())
    
    # Trigger sentinel sweep
    await sentinel.sweep_cycles()
    
    await asyncio.sleep(0.1)
    bus.stop()
    await bus_task
    
    assert len(closed_events) == 1
    assert closed_events[0].direction == "CLOSE"

@pytest.mark.asyncio
async def test_structural_kill(db_path, mock_mt5_api):
    bus = EventBus()
    ledger = CampaignLedger(bus)
    ledger.db_path = db_path
    await ledger.initialize()
    
    sentinel = TickSentinel(bus, None, ledger)
    await sentinel.start()
    
    cycle = await ledger.start_cycle(101, "BUY")
    cycle.state = "SWARM_FOLLOW"
    cycle.probe_ticket = 777
    cycle.set_tickets = [778]
    await ledger.save_cycle(cycle)
    
    # Mock MT5 position recent
    MockPos = namedtuple('MockPos', ['ticket', 'price_open', 'time', 'sl', 'volume'])
    mock_mt5_api.positions_get.return_value = (
        MockPos(ticket=777, price_open=1900.0, time=time.time() - 100, sl=0.0, volume=0.01),
    )
    MockTick = namedtuple('MockTick', ['bid', 'ask'])
    mock_mt5_api.symbol_info_tick.return_value = MockTick(bid=1900.0, ask=1900.5)
    
    MockSymbol = namedtuple('MockSymbol', ['point', 'trade_stops_level', 'swap_long', 'swap_short', 'swap_mode', 'spread', 'trade_tick_size', 'trade_tick_value'])
    mock_mt5_api.symbol_info.return_value = MockSymbol(point=0.01, trade_stops_level=10, swap_long=-1.0, swap_short=-1.0, swap_mode=0, spread=20, trade_tick_size=0.01, trade_tick_value=1.0)
    closed_events = []
    async def capture_close(event: OrderEvent):
        closed_events.append(event)
    bus.subscribe(OrderEvent, capture_close)
    
    bus_task = asyncio.create_task(bus.process_events())
    
    # Inject Structural Trend flip to BEARISH (opposite of BUY)
    await bus.publish(StructuralTrendEvent("GOLD", m15_trend="BEARISH", h1_trend="BULLISH", m15_close=1900, time=int(time.time())))
    await asyncio.sleep(0.05) # Allow handler to set self._latest_m15_trend
    
    # Trigger sentinel sweep
    await sentinel.sweep_cycles()
    
    await asyncio.sleep(0.1)
    bus.stop()
    await bus_task
    
    assert len(closed_events) == 2 # 1 for probe, 1 for set ticket
    assert cycle.state == "IDLE" # Should be liquidated before hard SL

@pytest.mark.asyncio
async def disabled_test_sentinel_collision_priority(db_path, mock_mt5_api):
    bus = EventBus()
    ledger = CampaignLedger(bus)
    ledger.db_path = db_path
    await ledger.initialize()
    
    sentinel = TickSentinel(bus, None, ledger)
    await sentinel.start()
    
    cycle = await ledger.start_cycle(102, "BUY")
    cycle.state = "SWARM_FOLLOW"
    cycle.probe_ticket = 888
    cycle.cycle_pnl = 15.0 # Target Hit condition
    await ledger.save_cycle(cycle)
    
    MockPos = namedtuple('MockPos', ['ticket', 'price_open', 'time', 'sl', 'volume'])
    mock_mt5_api.positions_get.return_value = (MockPos(ticket=888, price_open=1900.0, time=time.time() - 100, sl=0.0, volume=0.01),)
    MockTick = namedtuple('MockTick', ['bid', 'ask'])
    mock_mt5_api.symbol_info_tick.return_value = MockTick(bid=1900.0, ask=1900.5)
    MockSymbol = namedtuple('MockSymbol', ['point', 'trade_stops_level', 'swap_long', 'swap_short', 'swap_mode', 'spread', 'trade_tick_size', 'trade_tick_value'])
    mock_mt5_api.symbol_info.return_value = MockSymbol(point=0.01, trade_stops_level=10, swap_long=-1.0, swap_short=-1.0, swap_mode=0, spread=20, trade_tick_size=0.01, trade_tick_value=1.0)
    
    # Mock rates for ATR and ADX calculation
    mock_mt5_api.copy_rates_from_pos.return_value = tuple({'high': 1901.0, 'low': 1899.0, 'close': 1900.0} for _ in range(30))
    
    closed_events = []
    async def capture_close(event: OrderEvent):
        closed_events.append(event)
    bus.subscribe(OrderEvent, capture_close)
    
    target_hits = []
    async def capture_target(event):
        target_hits.append(event)
    from src.core.event_bus import TargetHitEvent
    bus.subscribe(TargetHitEvent, capture_target)
    
    bus_task = asyncio.create_task(bus.process_events())
    
    # Inject Structural Trend flip to BEARISH (Collision!)
    await bus.publish(StructuralTrendEvent("GOLD", m15_trend="BEARISH", h1_trend="BULLISH", m15_close=1900, time=int(time.time())))
    await asyncio.sleep(0.05)
    
    # Trigger sentinel sweep
    await sentinel.sweep_cycles()
    
    await asyncio.sleep(0.1)
    bus.stop()
    await bus_task
    
    assert len(target_hits) == 1
    assert len(closed_events) == 0 # Structural Kill should be completely bypassed!
