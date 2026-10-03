import asyncio
from src.core.telemetry_server import TelemetryServer
import urllib.request
import json

class MockRiskManager:
    def __init__(self):
        self._hwm = 10500.0
        self.session_start_equity = 10000.0
        self.target_multiplier = 2.0

class MockTickSentinel:
    def __init__(self):
        self._positions = {1: {}, 2: {}}

class MockAlphaScorer:
    def __init__(self):
        self.current_velocity = 4.5

class MockTelemetryState:
    def __init__(self):
        self.processing_latency_ms = 12.3

async def main():
    risk = MockRiskManager()
    sentinel = MockTickSentinel()
    scorer = MockAlphaScorer()
    state = MockTelemetryState()
    
    server = TelemetryServer(risk, sentinel, scorer, state)
    await server.start()
    
    await asyncio.sleep(1)
    
    try:
        req = urllib.request.urlopen("http://127.0.0.1:8080/status")
        res = req.read().decode('utf-8')
        print(json.dumps(json.loads(res), indent=2))
    except Exception as e:
        print(e)
        
    await server.stop()

if __name__ == '__main__':
    asyncio.run(main())
