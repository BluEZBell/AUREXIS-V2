import pytest
import asyncio
from unittest.mock import MagicMock
from src.core.event_bus import EventBus, OrderEvent
from src.core.campaign_ledger import CampaignLedger, CampaignCycle
import src.core.config as config
from collections import namedtuple

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_ledger.db")

@pytest.mark.asyncio
async def test_ledger_crash_recovery(db_path, mock_mt5_api):
    bus = EventBus()
    ledger = CampaignLedger(bus)
    ledger.db_path = db_path
    await ledger.initialize()
    
    # 1. Start cycle and log PROBE
    cycle = await ledger.start_cycle(12345, "BUY")
    cycle.state = "SCOUT_ACTIVE"
    cycle.probe_ticket = 999
    cycle.cycle_pnl = 15.5
    cycle.set_tickets = [1000, 1001]
    cycle.dispatched_events.add("SCOUT_SUCCESS")
    await ledger.save_cycle(cycle)
    
    # 2. Simulate Crash (create new instance)
    bus2 = EventBus()
    ledger2 = CampaignLedger(bus2)
    ledger2.db_path = db_path
    
    # Mock live positions to include our tickets so they aren't removed
    MockPos = namedtuple('MockPos', ['ticket', 'magic', 'profit'])
    mock_mt5_api.positions_get.return_value = (
        MockPos(ticket=999, magic=config.MAGIC_NUMBER, profit=10.0),
        MockPos(ticket=1000, magic=config.MAGIC_NUMBER, profit=5.0),
        MockPos(ticket=1001, magic=config.MAGIC_NUMBER, profit=0.5),
    )
    
    await ledger2.load_from_db()
    
    restored = ledger2.get_cycle(12345)
    assert restored is not None
    assert restored.direction == "BUY"
    assert restored.state == "SCOUT_ACTIVE"
    assert restored.probe_ticket == 999
    assert restored.cycle_pnl == 15.5
    assert set(restored.set_tickets) == {1000, 1001}
    assert "SCOUT_SUCCESS" in restored.dispatched_events

@pytest.mark.asyncio
async def test_orphan_adoption(db_path, mock_mt5_api):
    bus = EventBus()
    ledger = CampaignLedger(bus)
    ledger.db_path = db_path
    await ledger.initialize()
    
    closed_events = []
    async def capture_close(event: OrderEvent):
        if event.direction == "CLOSE":
            closed_events.append(event)
    bus.subscribe(OrderEvent, capture_close)
    
    # Mock MT5 to return a rogue ticket that has our magic number but is NOT in DB
    MockPos = namedtuple('MockPos', ['ticket', 'magic', 'profit', 'type'])
    import MetaTrader5 as mt5
    mock_mt5_api.POSITION_TYPE_BUY = mt5.POSITION_TYPE_BUY
    mock_mt5_api.POSITION_TYPE_SELL = mt5.POSITION_TYPE_SELL
    mock_mt5_api.positions_get.return_value = (
        MockPos(ticket=666, magic=config.MAGIC_NUMBER, profit=-5.0, type=mt5.POSITION_TYPE_BUY), # Rogue
    )
    
    MockTick = namedtuple('MockTick', ['bid', 'ask'])
    mock_mt5_api.symbol_info_tick.return_value = MockTick(bid=1900.0, ask=1900.5)
    
    await ledger.load_and_reconcile()
    
    # Give bus time to process
    bus_task = asyncio.create_task(bus.process_events())
    await asyncio.sleep(0.1)
    bus.stop()
    await bus_task
    
    # Should NOT have dispatched a CLOSE for ticket 666
    assert len(closed_events) == 0
    
    # Should have adopted the ticket into a new cycle
    adopted = False
    for cycle in ledger.active_cycles.values():
        if cycle.probe_ticket == 666:
            adopted = True
            assert cycle.state == "SCOUT_ACTIVE"
            assert cycle.direction == "BUY"
            break
            
    assert adopted
