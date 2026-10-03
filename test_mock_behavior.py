import asyncio
from unittest.mock import MagicMock, patch
import src.execution.bridge as bridge_module
from src.core.config import run_mt5_task
from src.core.event_bus import SignalEvent

async def test_minimal():
    class MockSymbol:
        point = 0.0001
        trade_tick_size = 0.0001
        trade_tick_value = 1.0

    mock_symbol_info = MockSymbol()
    
    with patch('src.execution.bridge.mt5.symbol_info', return_value=mock_symbol_info):
        import MetaTrader5 as mt5
        symbol_info = await run_mt5_task(mt5.symbol_info, "TEST")
        print("symbol_info:", type(symbol_info), symbol_info)
        
        point = getattr(symbol_info, 'point', 1e-5) if symbol_info else 1e-5
        tick_size = getattr(symbol_info, 'trade_tick_size', point) if symbol_info else point
        print("tick_size:", type(tick_size), tick_size)
        
if __name__ == '__main__':
    asyncio.run(test_minimal())
