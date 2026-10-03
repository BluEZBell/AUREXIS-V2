import re

with open('src/execution/bridge.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_close_retry = '''            if result and result.retcode in [mt5.TRADE_RETCODE_REQUOTE, mt5.TRADE_RETCODE_PRICE_OFF, mt5.TRADE_RETCODE_PRICE_CHANGED, mt5.TRADE_RETCODE_CONNECTION]:
                if attempt < 2:
                    logger.warning(f"Close retry {attempt+1}/3 due to retcode: {result.retcode}")
                    await asyncio.sleep(0.05)
                    continue'''

new_close_retry = '''            if result and result.retcode in [mt5.TRADE_RETCODE_REQUOTE, mt5.TRADE_RETCODE_PRICE_OFF, mt5.TRADE_RETCODE_PRICE_CHANGED, mt5.TRADE_RETCODE_CONNECTION]:
                if attempt < 2:
                    logger.warning(f"Close retry {attempt+1}/3 due to retcode: {result.retcode}")
                    continue'''

content = content.replace(old_close_retry, new_close_retry)


old_mod_retry = '''                logger.warning(f"Modify SL retry {attempt+1}/5 failed. Code: {result.retcode}")
                # Requotes or invalid stops due to fast market
                if result.retcode in [mt5.TRADE_RETCODE_REQUOTE, mt5.TRADE_RETCODE_PRICE_OFF, mt5.TRADE_RETCODE_PRICE_CHANGED, mt5.TRADE_RETCODE_CONNECTION, 10004, 10006, mt5.TRADE_RETCODE_INVALID_STOPS]:
                    await asyncio.sleep(0.1)
                    continue'''

new_mod_retry = '''                logger.warning(f"Modify SL retry {attempt+1}/5 failed. Code: {result.retcode}")
                # Requotes or invalid stops due to fast market
                if result.retcode in [mt5.TRADE_RETCODE_REQUOTE, mt5.TRADE_RETCODE_PRICE_OFF, mt5.TRADE_RETCODE_PRICE_CHANGED, mt5.TRADE_RETCODE_CONNECTION, 10004, 10006, mt5.TRADE_RETCODE_INVALID_STOPS]:
                    continue'''

content = content.replace(old_mod_retry, new_mod_retry)

with open('src/execution/bridge.py', 'w', encoding='utf-8') as f:
    f.write(content)
