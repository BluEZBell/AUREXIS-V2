import re

with open('src/core/alpha.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''    async def warmup(self, symbol: str) -> bool:
        logger.info(f"AlphaScorer Warm-Up bypassed for pure tick velocity.")
        return True'''

replacement = '''    async def warmup(self, symbol: str) -> bool:
        logger.info(f"Initiating Pre-Market Data Warm-Up for {symbol}...")
        
        timeframes = [
            ("M1", mt5.TIMEFRAME_M1),
            ("M15", mt5.TIMEFRAME_M15),
            ("H1", mt5.TIMEFRAME_H1)
        ]
        
        for tf_name, tf_value in timeframes:
            while True:
                logger.info(f"Fetching historical data for {symbol} [{tf_name}] (1000 bars)...")
                
                def _fetch_bars(tf=tf_value):
                    return mt5.copy_rates_from_pos(symbol, tf, 0, 1000)
                    
                rates = await run_mt5_task(_fetch_bars)
                
                if rates is not None and len(rates) > 0:
                    logger.info(f"Successfully retrieved {len(rates)} bars for {tf_name}.")
                    break
                else:
                    logger.warning(f"AWAITING_DATA: MT5 terminal is still downloading {tf_name} history for {symbol}. Retrying in 1 second...")
                    await asyncio.sleep(1)
        
        logger.info(f"Data Synchronizer Warm-Up complete! {symbol} is fully synchronized. HFT Engine ready.")
        return True'''

if target in content:
    content = content.replace(target, replacement)
    with open('src/core/alpha.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched warmup()")
else:
    print("Target not found. Let's try Regex.")

