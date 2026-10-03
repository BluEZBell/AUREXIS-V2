import MetaTrader5 as mt5
import sys

if __name__ == "__main__":
    print("Initializing mt5...")
    res = mt5.initialize()
    print(f"mt5 initialized: {res}")
    if res:
        mt5.shutdown()
    sys.exit(0)
