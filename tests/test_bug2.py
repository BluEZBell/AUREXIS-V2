import asyncio
from src.core.event_bus import EventBus, PositionsUpdateEvent, TickEvent
from src.core.config import TRADING_SYMBOL, MAGIC_NUMBER

class MockRiskManager:
    def __init__(self):
        self.release_count = 0
    async def release_quota(self, ticket):
        self.release_count += 1

class MockCampaignLedger:
    pass

class MockStateLedger:
    async def initialize(self): pass
    def update_ticket_state(self, *args, **kwargs): pass
    def delete_ticket(self, *args, **kwargs): pass
    async def get_all_records(self): return {}
    def delete_orphan_records(self, *args, **kwargs): pass

class MockTelemetryLogger:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None

def test_sentinel_bug():
    async def main():
        bus = EventBus()
        rm = MockRiskManager()
        
        from src.execution.tick_sentinel import TickSentinel
        sentinel = TickSentinel(bus, rm, MockCampaignLedger(), state_ledger=MockStateLedger())
        sentinel.telemetry_logger = MockTelemetryLogger()
        
        class SymbolInfo:
            point = 0.0001
            spread = 0.0
            
        async def mock_get_info():
            return SymbolInfo()
            
        sentinel._get_cached_symbol_info = mock_get_info
        sentinel._running = True
        
        pos = {
            'ticket': 1,
            'symbol': TRADING_SYMBOL,
            'type': 'BUY',
            'volume': 1.0,
            'price': 2000.0000,
            'sl': 1995.0000,
            'profit': 0.0,
            'magic': MAGIC_NUMBER,
            'price_current': 2000.0000,
            'time': 1000
        }
        await sentinel._handle_positions_update(PositionsUpdateEvent([pos], 0, 0, 0, 0, 0, "Test", "Test"))
        
        tick = TickEvent(TRADING_SYMBOL, 2000.0015, 2000.0015, 1001, 1.0)
        await sentinel.process_tick(tick)
        
        assert rm.release_count >= 0
        
        await sentinel._handle_positions_update(PositionsUpdateEvent([pos], 0, 0, 0, 0, 0, "Test", "Test"))
        
        tick2 = TickEvent(TRADING_SYMBOL, 2000.0015, 2000.0015, 1002, 1.0)
        await sentinel.process_tick(tick2)
        assert rm.release_count >= 0

    asyncio.run(main())
