import pytest
import sys
import asyncio
from unittest.mock import MagicMock

# Mock MT5 globally
mock_mt5 = MagicMock()
mock_mt5.TIMEFRAME_M5 = 5
mock_mt5.TIMEFRAME_M15 = 15
mock_mt5.TIMEFRAME_H1 = 60
mock_mt5.ORDER_TYPE_BUY = 0
mock_mt5.ORDER_TYPE_SELL = 1
sys.modules['MetaTrader5'] = mock_mt5

@pytest.fixture(autouse=True)
def mock_run_mt5_task(monkeypatch):
    async def fake_run_mt5_task(func, *args, **kwargs):
        # Call the function synchronously for testing purposes
        return func(*args, **kwargs)
    
    import src.core.config
    import src.execution.sentinel
    import src.strategy.alpha_harvester
    import src.core.campaign_ledger
    
    monkeypatch.setattr(src.core.config, "run_mt5_task", fake_run_mt5_task)
    monkeypatch.setattr(src.execution.sentinel, "run_mt5_task", fake_run_mt5_task)
    monkeypatch.setattr(src.strategy.alpha_harvester, "run_mt5_task", fake_run_mt5_task)
    monkeypatch.setattr(src.core.campaign_ledger, "run_mt5_task", fake_run_mt5_task)

@pytest.fixture
def mock_mt5_api():
    return mock_mt5
