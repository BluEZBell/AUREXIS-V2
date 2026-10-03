import sys
from unittest.mock import MagicMock

# Mock MetaTrader5 before importing
mt5_mock = MagicMock()
mt5_mock.initialize.return_value = False
mt5_mock.last_error.return_value = (-10005, 'IPC timeout')
sys.modules['MetaTrader5'] = mt5_mock

import asyncio
from src.core.event_bus import EventBus, ErrorEvent
from src.execution.bridge import MT5Bridge
from src.core.notifier import TelegramNotifier
from src.core.config import run_mt5_task

async def main():
    bus = EventBus()
    notifier = TelegramNotifier(bus)
    await notifier.start()
    
    # Track the published events
    published_events = []
    async def log_events(event):
        published_events.append(event)
        
    bus.subscribe(ErrorEvent, log_events)
    
    # We must start the event bus processing in the background so events actually get handled
    bus_task = asyncio.create_task(bus.process_events())
    
    bridge = MT5Bridge(bus)
    
    try:
        await bridge.initialize()
    except SystemExit as e:
        print(f"System exit caught: {e.code}")
    
    await asyncio.sleep(0.5)
    bus.stop()
    await bus_task
    
    print(f"Number of error events published: {len(published_events)}")
    for ev in published_events:
        print(ev)

if __name__ == '__main__':
    asyncio.run(main())
