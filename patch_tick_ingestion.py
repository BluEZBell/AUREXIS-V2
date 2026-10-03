import re

with open('src/strategy/alpha_harvester.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''                tick = mt5.symbol_info_tick(config.TRADING_SYMBOL)
                if tick and tick.time_msc > self._last_tick_time:'''

replacement = '''                tick = mt5.symbol_info_tick(config.TRADING_SYMBOL)
                if tick:
                    # Operation: Terminal Edge - Data Integrity Sanity Check (Bad Tick Filter)
                    if tick.bid >= tick.ask or tick.bid <= 0 or tick.ask <= 0:
                        logger.warning(f"BAD TICK REJECTED: Invalid spread/price anomaly (Bid: {tick.bid}, Ask: {tick.ask}).")
                        await asyncio.sleep(0)
                        continue
                        
                    if self._last_tick_bid > 0:
                        jump_points = abs(tick.bid - self._last_tick_bid) / point if point > 0 else 0
                        time_delta = (tick.time_msc - self._last_tick_time) / 1000.0 if self._last_tick_time > 0 else 1.0
                        
                        if jump_points > 500 and time_delta < 0.1:
                            logger.warning(f"CORRUPTED DATA SPIKE REJECTED: Price jumped {jump_points:.1f} points in {time_delta:.3f}s (Bid: {self._last_tick_bid} -> {tick.bid}).")
                            await asyncio.sleep(0)
                            continue
                            
                    self._last_tick_bid = tick.bid
                
                if tick and tick.time_msc > self._last_tick_time:'''

if target in content:
    content = content.replace(target, replacement)
    with open('src/strategy/alpha_harvester.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched tick ingestion logic in alpha_harvester.py")
else:
    print("Target not found.")

