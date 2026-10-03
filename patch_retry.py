import re

with open('src/execution/bridge.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''                        if result and result.retcode in [mt5.TRADE_RETCODE_CONNECTION, mt5.TRADE_RETCODE_REQUOTE, mt5.TRADE_RETCODE_PRICE_CHANGED, 10004, 10020, 10015, 10016]:
                            if retries_for_price < max_price_retries:
                                retries_for_price += 1
                                logger.warning(f"Order retry {retries_for_price}/{max_price_retries} due to requote/price change (retcode: {result.retcode})")
                                fresh_tick = await asyncio.to_thread(mt5.symbol_info_tick, req_payload['symbol'])
                                if fresh_tick:
                                    req_payload['price'] = fresh_tick.ask if req_payload['type'] == mt5.ORDER_TYPE_BUY else fresh_tick.bid
                                    symbol_info = await asyncio.to_thread(mt5.symbol_info, req_payload['symbol'])
                                    if symbol_info:
                                        req_payload['price'] = round(float(req_payload['price']), symbol_info.digits)
                                continue
                        break'''

replacement = '''                        if result and result.retcode in [mt5.TRADE_RETCODE_CONNECTION, mt5.TRADE_RETCODE_REQUOTE, mt5.TRADE_RETCODE_PRICE_CHANGED, mt5.TRADE_RETCODE_PRICE_OFF, 10004, 10008, 10009, 10020, 10015, 10016]:
                            if retries_for_price < max_price_retries:
                                retries_for_price += 1
                                logger.warning(f"Order retry {retries_for_price}/{max_price_retries} due to requote/price change (retcode: {result.retcode})")
                                # Operation: Terminal Edge - Aggressive Execution Retry Matrix micro-delay
                                await asyncio.sleep(0.02)
                                fresh_tick = await asyncio.to_thread(mt5.symbol_info_tick, req_payload['symbol'])
                                if fresh_tick:
                                    req_payload['price'] = fresh_tick.ask if req_payload['type'] == mt5.ORDER_TYPE_BUY else fresh_tick.bid
                                    symbol_info = await asyncio.to_thread(mt5.symbol_info, req_payload['symbol'])
                                    if symbol_info:
                                        req_payload['price'] = round(float(req_payload['price']), symbol_info.digits)
                                        # Recalculate Hard SL for new exact price
                                        atr_points = getattr(signal_event, "atr", 50.0)
                                        if atr_points <= 0: atr_points = 50.0
                                        hard_sl_dist = atr_points * 2.0 * symbol_info.point
                                        req_payload['sl'] = round(req_payload['price'] - hard_sl_dist, symbol_info.digits) if req_payload['type'] == mt5.ORDER_TYPE_BUY else round(req_payload['price'] + hard_sl_dist, symbol_info.digits)
                                continue
                            else:
                                logger.error(f"TERMINAL REJECTION: Failed to execute after {max_price_retries} attempts.")
                        break'''

if target in content:
    content = content.replace(target, replacement)
    with open('src/execution/bridge.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched retry loop in bridge.py")
else:
    print("Target not found.")

