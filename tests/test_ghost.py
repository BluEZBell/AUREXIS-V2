import pytest
import asyncio
from src.core.event_bus import EventBus, TickEvent, OrderEvent, PositionsUpdateEvent
from src.execution.tick_sentinel import TickSentinel

class MockRisk: pass
class MockLedger: pass

@pytest.mark.asyncio
async def test_ghost_tp():
    from src.execution.tick_sentinel import TickSentinel
    from src.core.config import TRADING_SYMBOL, MAGIC_NUMBER
    from collections import namedtuple
    bus = EventBus()
    sentinel = TickSentinel(bus, MockRisk(), MockLedger())
    
    # Mock the cached symbol info to prevent MagicMock math errors
    SymbolInfo = namedtuple('SymbolInfo', ['point', 'spread', 'swap_long', 'swap_short'])
    async def mock_get_info():
        return SymbolInfo(0.00001, 10, 0, 0)
    sentinel._get_cached_symbol_info = mock_get_info
    
    await sentinel.start()
    
    await sentinel._handle_order_event(OrderEvent(
        ticket=1, symbol=TRADING_SYMBOL, direction='BUY', volume=1.0, 
        price=100.0, status='FILLED', cycle_id=0, soft_sl=90.0, soft_tp=110.0))
        
    await sentinel._handle_positions_update(PositionsUpdateEvent(
        [{'ticket': 1, 'type': 'BUY', 'price': 100.0, 'magic': MAGIC_NUMBER}], 
        0,0,0,0,0,'',''))
        
    await sentinel.process_tick(TickEvent(TRADING_SYMBOL, 111.0, 111.0, 0, 1.0))
    assert 1 in sentinel._closing_tickets
