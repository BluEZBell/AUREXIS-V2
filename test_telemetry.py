import asyncio
from aiohttp import ClientSession
from src.core.telemetry_server import TelemetryServer
import os

import pytest

@pytest.mark.asyncio
async def test():
    class Dummy:
        pass
    
    server = TelemetryServer(Dummy(), Dummy(), Dummy(), Dummy(), None)
    await server.start()
    
    async with ClientSession() as session:
        async with session.get('http://127.0.0.1:8080/') as resp:
            print('Status:', resp.status)
            print('Content-Type:', resp.headers.get('Content-Type'))
            
            if resp.status == 200:
                text = await resp.text()
                print('Content length:', len(text))
            
    await server.stop()
