import re

with open('src/execution/bridge.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''                # Floor and Cap deviation
                dev = max(10, min(200, dev))
                
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": str(symbol),
                    "volume": float(volume),
                    "type": int(action),
                    "price": round(float(price), digits),
                    "sl": 0.0,
                    "tp": 0.0,
                    "deviation": int(dev),
                    "magic": int(MAGIC_NUMBER),'''

replacement = '''                # Floor and Cap deviation
                dev = max(10, min(200, dev))
                
                # Operation: HFT Aggression - Naked Order Protection (Hard Catastrophic SL)
                hard_sl_dist = atr_points * 2.0 * symbol_info.point
                hard_sl = round(price - hard_sl_dist, digits) if action == mt5.ORDER_TYPE_BUY else round(price + hard_sl_dist, digits)
                
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": str(symbol),
                    "volume": float(volume),
                    "type": int(action),
                    "price": round(float(price), digits),
                    "sl": float(hard_sl),
                    "tp": 0.0,
                    "deviation": int(dev),
                    "magic": int(MAGIC_NUMBER),'''

if target in content:
    content = content.replace(target, replacement)
    with open('src/execution/bridge.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched Naked Order Protection in bridge.py")
else:
    print("Target not found.")

