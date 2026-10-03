import asyncio
from collections import deque
import time

class AlphaScorer:
    def __init__(self):
        self.tick_timestamps = deque(maxlen=20)
        
    async def evaluate_tick_prior(self, now: float) -> float:
        self.tick_timestamps.append(now)
        velocity = 0.0
        if len(self.tick_timestamps) > 1:
            dt = now - self.tick_timestamps[0]
            if dt > 0:
                velocity = (len(self.tick_timestamps) - 1) / dt
        return velocity

import pytest

@pytest.mark.asyncio
async def test_prior():
    scorer = AlphaScorer()
    
    # 20 ticks at 10 ticks/second
    now = 1000.0
    for i in range(20):
        v = await scorer.evaluate_tick_prior(now)
        now += 0.1
    print(f"Velocity before pause: {v}")
    
    # Pause for 10 minutes
    now += 600.0
    
    # Surge at 100 ticks/second
    print("Surge starts...")
    for i in range(5):
        v = await scorer.evaluate_tick_prior(now)
        print(f"Tick {i+1} velocity: {v}")
        now += 0.01
