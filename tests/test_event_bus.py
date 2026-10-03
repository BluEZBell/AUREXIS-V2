import pytest
import asyncio
from src.core.event_bus import EventBus, TickEvent

@pytest.mark.asyncio
async def test_event_bus_concurrency():
    bus = EventBus()
    processed_count = 0
    
    async def dummy_handler(event):
        nonlocal processed_count
        processed_count += 1

    bus.subscribe(TickEvent, dummy_handler)
    
    # Start the bus
    bus_task = asyncio.create_task(bus.process_events())
    
    # Publish 10,000 events
    for i in range(10000):
        await bus.publish(TickEvent("GOLD", 100.0, 100.1, 100000 + i))
        
    # Wait for processing
    await asyncio.sleep(0.5)
    bus.stop()
    await bus_task
    
    assert processed_count == 10000, f"Expected 10000, got {processed_count}"

@pytest.mark.asyncio
async def test_event_bus_exception_handling():
    bus = EventBus()
    processed_count = 0
    
    async def crashing_handler(event):
        raise ValueError("Simulated Crash")
        
    async def safe_handler(event):
        nonlocal processed_count
        processed_count += 1
        
    bus.subscribe(TickEvent, crashing_handler)
    bus.subscribe(TickEvent, safe_handler)
    
    bus_task = asyncio.create_task(bus.process_events())
    
    # Publish an event; crashing_handler will fail, but safe_handler should still succeed
    # and the loop shouldn't die.
    await bus.publish(TickEvent("GOLD", 100.0, 100.1, 100000))
    await bus.publish(TickEvent("GOLD", 100.0, 100.1, 100001))
    
    await asyncio.sleep(0.1)
    bus.stop()
    await bus_task
    
    assert processed_count == 2, f"Expected safe handler to run twice, ran {processed_count} times."
