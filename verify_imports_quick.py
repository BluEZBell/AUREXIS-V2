import sys
import asyncio

async def test_imports():
    from src.core.event_bus import EventBus
    from src.strategy.alpha_harvester import AlphaHarvesterStrategy
    from src.web.app import app, _broadcast_event
    from src.execution.sentinel import TickSentinel
    print("Imports successful!")

if __name__ == "__main__":
    asyncio.run(test_imports())
