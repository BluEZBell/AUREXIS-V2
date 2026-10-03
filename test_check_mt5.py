import MetaTrader5 as mt5

def test_print_constants():
    print(f"FOK: {mt5.ORDER_FILLING_FOK}")
    print(f"IOC: {mt5.ORDER_FILLING_IOC}")
    print(f"RETURN: {mt5.ORDER_FILLING_RETURN}")
