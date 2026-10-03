import pytest
import time
import asyncio
from unittest.mock import MagicMock
from collections import namedtuple

from src.strategy.alpha_harvester import DataIntegrityFilter

@pytest.mark.asyncio
async def test_filter_zero_pricing():
    f = DataIntegrityFilter()
    tick = namedtuple('Tick', ['bid', 'ask', 'time_msc'])(bid=0.0, ask=1.0, time_msc=int(time.time()*1000))
    assert await f.validate_tick(tick, 10.0) == False

@pytest.mark.asyncio
async def test_filter_negative_spread():
    f = DataIntegrityFilter()
    tick = namedtuple('Tick', ['bid', 'ask', 'time_msc'])(bid=1.5, ask=1.4, time_msc=int(time.time()*1000))
    assert await f.validate_tick(tick, 10.0) == False

@pytest.mark.asyncio
async def test_filter_micro_gap():
    f = DataIntegrityFilter()
    tick1 = namedtuple('Tick', ['bid', 'ask', 'time_msc'])(bid=100.0, ask=101.0, time_msc=int(time.time()*1000))
    assert await f.validate_tick(tick1, 10.0) == True
    
    tick2 = namedtuple('Tick', ['bid', 'ask', 'time_msc'])(bid=150.0, ask=151.0, time_msc=int(time.time()*1000))
    # With 5x threshold, a jump of 50.0 (where ATR=10.0 => threshold is 50.0) is not strictly > 50.0
    assert await f.validate_tick(tick2, 10.0) == True

@pytest.mark.asyncio
async def test_filter_micro_gap_low_atr():
    f = DataIntegrityFilter()
    tick1 = namedtuple('Tick', ['bid', 'ask', 'time_msc'])(bid=100.0, ask=101.0, time_msc=int(time.time()*1000))
    assert await f.validate_tick(tick1, 10.0) == True
    
    tick2 = namedtuple('Tick', ['bid', 'ask', 'time_msc'])(bid=100.1, ask=101.1, time_msc=int(time.time()*1000))
    # Jump is 0.1, ATR is 0.01. Effective ATR is 0.05. 5 * 0.05 = 0.25. 0.1 > 0.25 is False. Accepted.
    assert await f.validate_tick(tick2, 0.01) == True

@pytest.mark.asyncio
async def test_stale_tick():
    f = DataIntegrityFilter()
    # broker is 2 hours behind UTC
    broker_time = int(time.time()*1000) - 2 * 3600 * 1000
    tick = namedtuple('Tick', ['bid', 'ask', 'time_msc'])(bid=100.0, ask=101.0, time_msc=broker_time)
    # Stale tick should be accepted if it matches broker offset.
    assert await f.validate_tick(tick, 10.0) == True
