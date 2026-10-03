import sys
from unittest.mock import MagicMock

# Mock MetaTrader5 before importing
mt5_mock = MagicMock()
mt5_mock.initialize.return_value = False
sys.modules['MetaTrader5'] = mt5_mock

import MetaTrader5 as mt5

try:
    mt5.initialize(path=None)
    print("path=None works with mock")
except Exception as e:
    print(f"Exception: {e}")

