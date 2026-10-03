import asyncio
import os
import sys

# add path to import src
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.execution.risk_manager import RiskManager
from src.core.event_bus import EventBus
import src.core.config as config

import pytest

@pytest.mark.asyncio
async def test_roi_vault():
    config.INITIAL_ACCOUNT_BALANCE = 100.0
    config.DRAWDOWN_TYPE = "EQUITY_TRAILING"
    config.MAX_OVERALL_DRAWDOWN_PCT = 10.0
    
    event_bus = EventBus()
    rm = RiskManager(event_bus, live_balance=1000.0)
    
    # We will simulate events being processed
    asyncio.create_task(event_bus.process_events())
    
    # Simulate equity reaching 200 (100% ROI)
    print("Testing check_drawdown_limits with equity = 200.0 (100% ROI)")
    res = await rm.check_drawdown_limits(current_equity=200.0, start_equity=100.0)
    print(f"check_drawdown_limits returned: {res}")
    
    print(f"Vault Secured: {rm._vault_secured}")
    print(f"Vault Floor: {rm._vault_floor}")
    
    # Check lot size calculation
    print("Testing calculate_lot_size with equity = 210.0")
    # Need to mock mt5 calls
    # We will just patch mt5 for testing
    import MetaTrader5 as mt5
    class MockSymbolInfo:
        swap_long = 0.0
        swap_short = 0.0
        spread = 0.0
        point = 1e-5
        trade_tick_size = 1e-5
        trade_tick_value = 1.0
        volume_step = 0.01
        volume_min = 0.01
        volume_max = 100.0
    from unittest.mock import patch
    
    with patch('MetaTrader5.symbol_info', lambda *args, **kwargs: MockSymbolInfo()), \
         patch('MetaTrader5.positions_get', lambda *args, **kwargs: []), \
         patch('MetaTrader5.account_info', lambda *args, **kwargs: type("MockAccountInfo", (), {"margin_free": 1000.0, "equity": 210.0})()), \
         patch('MetaTrader5.symbol_info_tick', lambda *args, **kwargs: type("MockTick", (), {"ask": 1.0, "bid": 1.0})()), \
         patch('MetaTrader5.order_calc_margin', lambda *args, **kwargs: 10.0):
         
        # also need to mock config.TRADING_SYMBOL
        config.TRADING_SYMBOL = "EURUSD"
        config.MAGIC_NUMBER = 12345
        
        lot = await rm.calculate_lot_size(equity=210.0)
        print(f"Calculated lot size for 210 equity (excess 105): {lot}")
        
        # Check lot size calculation for equity below floor
        lot_zero = await rm.calculate_lot_size(equity=100.0)
        print(f"Calculated lot size for 100 equity: {lot_zero}")
    
    print("Testing check_drawdown_limits with equity = 104.0 (Breached floor)")
    res2 = await rm.check_drawdown_limits(current_equity=104.0, start_equity=210.0)
    print(f"check_drawdown_limits when breached returned: {res2}")
    
    await asyncio.sleep(1)
    event_bus.stop()

if __name__ == "__main__":
    asyncio.run(test_roi_vault())
