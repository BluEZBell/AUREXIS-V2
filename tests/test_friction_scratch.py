import asyncio
from src.core.event_bus import EventBus, OrderEvent, RiskAlertEvent
from src.execution.dynamic_friction import DynamicFrictionEngine
import MetaTrader5 as mt5

class MockSymbolInfo:
    def __init__(self):
        self.point = 0.01

import pytest

@pytest.mark.asyncio
async def test_friction():
    bus = EventBus()
    engine = DynamicFrictionEngine(bus)
    
    # Mock mt5 task
    async def mock_run_mt5_task(func):
        return MockSymbolInfo()
    
    import src.execution.dynamic_friction as df
    df.run_mt5_task = mock_run_mt5_task
    
    # Subscribe to RiskAlertEvent
    alerts = []
    async def capture_alert(event):
        alerts.append(event)
    bus.subscribe(RiskAlertEvent, capture_alert)
    
    bus_task = asyncio.create_task(bus.process_events())
    
    # Send order events
    events = [
        OrderEvent(ticket=1, symbol="TEST", direction="BUY", volume=0.1, price=1.05, status="FILLED", requested_price=1.00),
        OrderEvent(ticket=2, symbol="TEST", direction="BUY", volume=0.1, price=1.10, status="FILLED", requested_price=1.00),
        OrderEvent(ticket=3, symbol="TEST", direction="BUY", volume=0.1, price=1.20, status="FILLED", requested_price=1.00),
    ]
    
    for ev in events:
        await bus.publish(ev)
        
    await asyncio.sleep(0.1)
    
    print(f"Slippage history: {engine.slippage_history}")
    print(f"Dynamic offset: {engine.get_dynamic_offset()}")
    print(f"Alerts: {len(alerts)}")
    
    bus.stop()
    await bus_task

if __name__ == "__main__":
    asyncio.run(test_friction())
