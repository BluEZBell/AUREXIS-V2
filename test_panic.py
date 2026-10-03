import asyncio
from src.core.event_bus import EventBus, ErrorEvent
from src.execution.risk_manager import RiskManager

async def dummy_handle_error(event):
    print(f"Dummy bridge received: {event.message}")
    await asyncio.sleep(1.0)
    print("Dummy bridge successfully closed positions.")

async def panic_halt_handler(event):
    if event.critical:
        print(f"CRITICAL ERROR CAUGHT: {event.message}. TRIGGERING CATASTROPHIC SHUTDOWN.")
        await asyncio.sleep(2.0)
        print("OS Exit triggered.")
        import os
        os._exit(1)

async def main():
    bus = EventBus()
    bus.subscribe(ErrorEvent, panic_halt_handler)
    bus.subscribe(ErrorEvent, dummy_handle_error)

    asyncio.create_task(bus.process_events())
    
    rm = RiskManager(bus, live_balance=1000.0)
    print("Checking drawdown limits...")
    # This should trigger MAX DAILY LOSS EXCEEDED (100 -> 90 is 10% loss)
    # wait, MAX_DAILY_LOSS_PCT is 4.5
    # we need to simulate PROFILE_MODE='EXAM_MODE' which is hardcoded?
    await rm.check_drawdown_limits(current_equity=90, start_equity=100)
    
    await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
