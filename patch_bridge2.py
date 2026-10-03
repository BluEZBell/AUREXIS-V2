import re

with open('src/execution/bridge.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_execute_order = '''                digits = symbol_info.digits
                
                dev = 100 if getattr(signal, "conviction", 0.0) >= 50.0 else 50
                # Eradicated 500-point broker hard stop loss - relying dynamically on TickSentinel
                
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": str(symbol),
                    "volume": float(volume),
                    "type": int(action),
                    "price": round(float(price), digits),
                    "sl": 0.0,
                    "tp": 0.0,
                    "deviation": int(dev),
                    "magic": int(MAGIC_NUMBER),
                    "comment": f"AUREXIS {getattr(signal, 'strategy_id', 'UNKN')}",
                    "type_time": int(mt5.ORDER_TIME_GTC),
                    "type_filling": int(mt5.ORDER_FILLING_IOC),
                }'''

new_execute_order = '''                digits = symbol_info.digits
                
                # Dynamic Deviation Control
                atr_points = getattr(signal, "atr", 50.0)
                if atr_points <= 0:
                    atr_points = 50.0
                
                # Calculate Tick Velocity
                ticks = mt5.copy_ticks_from(symbol, tick_info.time, 20, mt5.COPY_TICKS_ALL)
                velocity_points = 0.0
                if ticks is not None and len(ticks) >= 20:
                    velocity_points = abs(ticks[-1]['ask'] - ticks[0]['bid']) / symbol_info.point
                
                # High momentum = wider deviation (e.g. 50% of ATR). Low momentum = tight deviation (10% of ATR).
                if velocity_points > (atr_points * 0.2):
                    dev = int(atr_points * 0.5)
                else:
                    dev = int(atr_points * 0.1)
                
                # Floor and Cap deviation
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
                    "magic": int(MAGIC_NUMBER),
                    "comment": f"AUREXIS {getattr(signal, 'strategy_id', 'UNKN')}",
                    "type_time": int(mt5.ORDER_TIME_GTC),
                    "type_filling": int(mt5.ORDER_FILLING_IOC),
                }'''

content = content.replace(old_execute_order, new_execute_order)

old_retry = '''                        if result and result.retcode in [mt5.TRADE_RETCODE_CONNECTION, 10004, 10015, 10016]:
                            if retries_for_price < max_price_retries:
                                retries_for_price += 1
                                logger.warning(f"Order retry {retries_for_price}/{max_price_retries} due to retcode: {result.retcode}")'''

new_retry = '''                        if result and result.retcode in [mt5.TRADE_RETCODE_CONNECTION, mt5.TRADE_RETCODE_REQUOTE, mt5.TRADE_RETCODE_PRICE_CHANGED, 10004, 10020, 10015, 10016]:
                            if retries_for_price < max_price_retries:
                                retries_for_price += 1
                                logger.warning(f"Order retry {retries_for_price}/{max_price_retries} due to requote/price change (retcode: {result.retcode})")'''

content = content.replace(old_retry, new_retry)

with open('src/execution/bridge.py', 'w', encoding='utf-8') as f:
    f.write(content)
