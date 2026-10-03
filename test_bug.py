import asyncio
from src.core.event_bus import EventBus, PositionsUpdateEvent, TickEvent

class MockRiskManager:
    def __init__(self):
        self.release_count = 0
    def release_quota(self, ticket):
        self.release_count += 1
        return asyncio.sleep(0)

class MockCampaignLedger:
    pass

class MockTelemetryLogger:
    def record_sentinel_event(self, **kwargs):
        pass

async def main():
    bus = EventBus()
    rm = MockRiskManager()
    
    from src.execution.tick_sentinel import TickSentinel
    sentinel = TickSentinel(bus, rm, MockCampaignLedger())
    sentinel.telemetry_logger = MockTelemetryLogger()
    
    # Mock _get_cached_symbol_info
    class SymbolInfo:
        point = 0.0001
    sentinel._get_cached_symbol_info = lambda: asyncio.sleep(0, result=SymbolInfo())
    sentinel._running = True
    
    # Simulate PositionsUpdateEvent with catastrophic SL (e.g., 500 points away)
    pos = {
        'ticket': 1,
        'symbol': 'XAUUSD',
        'type': 'BUY',
        'volume': 1.0,
        'price': 2000.0000,
        'sl': 1995.0000, # Catastrophic SL
        'profit': 0.0,
        'magic': 123456,
        'price_current': 2000.0000,
        'time': 1000
    }
    await sentinel._handle_positions_update(PositionsUpdateEvent([pos], 0, 0, 0, 0, 0, "Test", "Test"))
    
    # Tick 1: Price goes up by 15 points (0.0015)
    tick = TickEvent('XAUUSD', 1001, 2000.0015, 2000.0015, 1.0)
    await sentinel.process_tick(tick)
    print("Release count after Tick 1:", rm.release_count)
    
    # Position updates from MT5 (still has catastrophic SL)
    await sentinel._handle_positions_update(PositionsUpdateEvent([pos], 0, 0, 0, 0, 0, "Test", "Test"))
    
    # Tick 2: Price still up
    tick2 = TickEvent('XAUUSD', 1002, 2000.0015, 2000.0015, 1.0)
    await sentinel.process_tick(tick2)
    print("Release count after Tick 2:", rm.release_count)

asyncio.run(main())
