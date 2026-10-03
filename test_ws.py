import asyncio
import json
import dataclasses
import websockets
from src.core.telemetry_server import TelemetryServer

@dataclasses.dataclass
class TickEvent:
    bid: float = 4255.86
    ask: float = 4256.40

@dataclasses.dataclass
class StructuralTrendEvent:
    h1_trend: str = "BULLISH"
    m15_trend: str = "BEARISH"
    m15_adx: float = 29.6
    m15_rsi: float = 30.8

class DummyEventBus:
    def __init__(self):
        self.handlers = {}
    def subscribe(self, event_type, handler):
        self.handlers[event_type.__name__] = handler
    async def publish(self, event):
        handler = self.handlers.get(type(event).__name__)
        if handler:
            await handler(event)

import pytest

@pytest.mark.asyncio
async def test_main():
    bus = DummyEventBus()
    server = TelemetryServer(None, None, None, None, event_bus=bus)
    await server.start()
    
    # Connect websocket
    async with websockets.connect("ws://127.0.0.1:8080/ws/telemetry") as ws:
        # Publish structural trend
        await bus.publish(StructuralTrendEvent())
        
        # Publish tick
        await bus.publish(TickEvent())
        
        # Read from websocket
        msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
        print("Received:", msg)
        
        msg2 = await asyncio.wait_for(ws.recv(), timeout=2.0)
        print("Received2:", msg2)

    await server.stop()

