import asyncio
from src.core.event_bus import EventBus, PositionsUpdateEvent, TickEvent
from src.core.config import TRADING_SYMBOL, MAGIC_NUMBER

class MockRiskManager:
    def __init__(self):
        self.release_count = 0
    def release_quota(self, ticket):
        self.release_count += 1
        return asyncio.sleep(0)

class MockCampaignLedger:
    pass

class MockTelemetryLogger:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None

def test_sentinel_bug():
    async def main():
        bus = EventBus()
        rm = MockRiskManager()
        
        from src.execution.tick_sentinel import TickSentinel
        sentinel = TickSentinel(bus, rm, MockCampaignLedger())
        sentinel.telemetry_logger = MockTelemetryLogger()
        
        class SymbolInfo:
            point = 0.0001
            
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
        assert rm.release_count == 1, f"Expected 1, got {rm.release_count}"
        
        await sentinel._handle_positions_update(PositionsUpdateEvent([pos], 0, 0, 0, 0, 0, "Test", "Test"))
        
        tick2 = TickEvent(TRADING_SYMBOL, 2000.0015, 2000.0015, 1002, 1.0)
        await sentinel.process_tick(tick2)
        assert rm.release_count == 1, f"Bug present! Release count increased to {rm.release_count}"

    asyncio.run(main())
