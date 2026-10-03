import sys
import unittest.mock as mock

mt5_mock = mock.MagicMock()
mt5_mock.initialize.return_value = True
mt5_mock.copy_ticks_from.return_value = [
    {'time': 1600000000, 'bid': 1.1000, 'ask': 1.1001, 'volume': 1.0},
    {'time': 1600000001, 'bid': 1.1010, 'ask': 1.1011, 'volume': 2.0},
    {'time': 1600000002, 'bid': 1.1020, 'ask': 1.1021, 'volume': 1.0},
    {'time': 1600000003, 'bid': 1.0900, 'ask': 1.0901, 'volume': 3.0}
] * 25000  # 100000 ticks

# Mock the structured array behavior
class DummyTicks(list):
    @property
    def dtype(self):
        class Dtype:
            names = ('time', 'bid', 'ask', 'volume')
        return Dtype()

mt5_mock.copy_ticks_from.return_value = DummyTicks(mt5_mock.copy_ticks_from.return_value)
mt5_mock.symbol_info_tick.return_value = mock.MagicMock(bid=1.1, ask=1.1001, volume_real=1.0)
mt5_mock.symbol_info.return_value = mock.MagicMock(point=0.00001)
mt5_mock.TIMEFRAME_M15 = 15
mt5_mock.TIMEFRAME_H1 = 60
mt5_mock.copy_rates_from_pos.return_value = [{'close': 1.1}] * 50

sys.modules['MetaTrader5'] = mt5_mock

import asyncio
from src.tools.tick_replay import run_replay_engine
import src.core.config as config

async def main():
    await run_replay_engine("EURUSD")

asyncio.run(main())
