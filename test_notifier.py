import asyncio
import os
from src.core.event_bus import EventBus, OrderEvent, StructuralTrendEvent, MilestoneEvent, ErrorEvent
from src.core.notifier import TelegramNotifier

async def main():
    bus = EventBus()
    notifier = TelegramNotifier(bus)
    await notifier.start()

    print(f"Notifier running: {notifier._running}")

    # Fire event
    await bus.publish(OrderEvent(ticket=1, symbol="EURUSD", direction="BUY", volume=0.1, price=1.1, status="FILLED"))
    
    # Process events in background
    t = asyncio.create_task(bus.process_events())
    await asyncio.sleep(1)

    bus.stop()
    await t
    await notifier.stop()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
