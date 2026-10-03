import re

with open('src/execution/bridge.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_close = '''            digits = symbol_info.digits
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "volume": float(volume),
                "type": action,
                "price": round(float(price), digits),
                "deviation": 50,
                "magic": MAGIC_NUMBER,
                "comment": "AUREXIS CLOSE",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC if order_type == "IOC" else self._get_filling_mode(pos.symbol),
            }'''

new_close = '''            digits = symbol_info.digits
            
            atr_points = self._latest_m15_atr if getattr(self, '_latest_m15_atr', 0) > 0 else 50.0
            ticks = mt5.copy_ticks_from(pos.symbol, tick.time, 20, mt5.COPY_TICKS_ALL)
            if ticks is not None and len(ticks) >= 20:
                vel = abs(ticks[-1]['ask'] - ticks[0]['bid']) / symbol_info.point
            else:
                vel = 0.0
            dev = int(atr_points * 0.5) if vel > (atr_points * 0.2) else int(atr_points * 0.1)
            dev = max(10, min(200, dev))
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "volume": float(volume),
                "type": action,
                "price": round(float(price), digits),
                "deviation": dev,
                "magic": MAGIC_NUMBER,
                "comment": "AUREXIS CLOSE",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC if order_type == "IOC" else self._get_filling_mode(pos.symbol),
            }'''

content = content.replace(old_close, new_close)

old_mod = '''            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "symbol": symbol,
                "sl": round(float(target_sl), digits),
                "tp": round(float(existing_tp), digits),
                "deviation": 30,
                "magic": MAGIC_NUMBER
            }'''

new_mod = '''            atr_points = getattr(self, '_latest_m15_atr', 50.0)
            if atr_points <= 0: atr_points = 50.0
            dev = int(atr_points * 0.1)
            dev = max(10, min(100, dev))
            
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "symbol": symbol,
                "sl": round(float(target_sl), digits),
                "tp": round(float(existing_tp), digits),
                "deviation": dev,
                "magic": MAGIC_NUMBER
            }'''

content = content.replace(old_mod, new_mod)

with open('src/execution/bridge.py', 'w', encoding='utf-8') as f:
    f.write(content)
