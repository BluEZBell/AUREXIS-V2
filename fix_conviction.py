import re

with open('src/strategy/alpha_harvester.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Rewrite _calculate_conviction
conviction_old = r'''    async def _calculate_conviction\(self, direction: str, chop_score: int = 0\) -> float:.*?(?=    async def get_indicators)'''

conviction_new = r'''    async def _calculate_conviction(self, direction: str, chop_score: int = 0) -> float:
        score = 0.0  # Base score
        
        ind = self._latest_indicators.get(config.TRADING_SYMBOL)
        if not ind:
            return 0.0
            
        curr_price = ind.get('curr_price', 0.0)
        ema20_m15 = ind.get('ema_20', 0.0)
        rsi = ind.get('rsi', 50.0)
        bb_upper = ind.get('bb_upper', 0.0)
        bb_lower = ind.get('bb_lower', 0.0)
        adx_m15 = ind.get('adx_m15', 0.0)
        macd_hist = ind.get('macd_hist', 0.0)
        
        if chop_score < 3:
            # PATH A: TREND_MODE (Strict Springboard Sniper)
            if direction == "BUY":
                if ema20_m15 > 0 and curr_price <= ema20_m15 * 1.0005 and curr_price >= ema20_m15 * 0.9990 and 35 <= rsi <= 58:
                    score += 50.0
                if rsi > 60:
                    score -= 100.0
            else:
                if ema20_m15 > 0 and curr_price >= ema20_m15 * 0.9995 and curr_price <= ema20_m15 * 1.0010 and 42 <= rsi <= 65:
                    score += 50.0
                if rsi < 40:
                    score -= 100.0
                    
            if self._latest_structure:
                h1 = self._latest_structure.h1_trend
                m15 = self._latest_structure.m15_trend
                if direction == "BUY":
                    if h1 == "BULLISH" and m15 == "BULLISH":
                        score += 30.0
                    elif h1 == "BEARISH" or m15 == "BEARISH":
                        score -= 20.0
                else:
                    if h1 == "BEARISH" and m15 == "BEARISH":
                        score += 30.0
                    elif h1 == "BULLISH" or m15 == "BULLISH":
                        score -= 20.0
                        
            if adx_m15 > 22.0:
                if direction == "BUY" and macd_hist > 0:
                    score += 20.0
                elif direction == "SELL" and macd_hist < 0:
                    score += 20.0
        else:
            # PATH B: RANGE_MODE (Strict Mean-Reversion)
            if direction == "BUY":
                if curr_price <= bb_lower + (bb_upper - bb_lower) * 0.1 and rsi < 45:
                    score += 50.0
                if rsi > 50 or curr_price >= bb_upper - (bb_upper - bb_lower) * 0.1:
                    score -= 100.0
            else:
                if curr_price >= bb_upper - (bb_upper - bb_lower) * 0.1 and rsi > 55:
                    score += 50.0
                if rsi < 50 or curr_price <= bb_lower + (bb_upper - bb_lower) * 0.1:
                    score -= 100.0

        return max(0.0, min(100.0, score))
            
'''
content = re.sub(conviction_old, conviction_new, content, flags=re.DOTALL)

# 2. Update process_tick (Scout Entry Triggers)
scout_old = r'''                # SCOUT Entry Logic (Forked for Trend vs Range)
                if chop_score < 3:
                    # Trend Mode Scout
                    if ind['adx'] < 18 or (48 <= ind['rsi'] <= 52):
                        return
                    direction = "BUY" if ind['ema20_m15'] > ind['ema50_m15'] and ind['rsi'] > 55 else "SELL"
                    if direction == "SELL" and not (ind['ema20_m15'] < ind['ema50_m15'] and ind['rsi'] < 45):
                        return
                else:
                    # Range Mode Scout (Mean Reversion)
                    # Don't require ADX>18, we want chopped markets.
                    curr = ind.get('curr_price', 0.0)
                    bb_up = ind.get('bb_upper', 0.0)
                    bb_low = ind.get('bb_lower', 0.0)
                    rsi = ind.get('rsi', 50.0)
                    if curr <= bb_low + (bb_up - bb_low) * 0.1 and rsi < 45:
                        direction = "BUY"
                    elif curr >= bb_up - (bb_up - bb_low) * 0.1 and rsi > 55:
                        direction = "SELL"
                    else:
                        return # No range extremes met
                    
                cycle_id = int(time.time())
                logger.info(f"SCOUT ENTRY: {direction}. Initializing Cycle {cycle_id}")
                conv = await self._calculate_conviction(direction, chop_score)
                sig = SignalEvent(event.symbol, direction, self.strategy_id, event.bid, conviction=conv, volume=0.10, cycle_id=cycle_id, order_type="PROBE")'''

scout_new = r'''                # SCOUT Entry Logic (Forked for Trend vs Range)
                if chop_score < 3:
                    # Trend Mode Scout
                    if ind['adx'] < 18 or (48 <= ind['rsi'] <= 52):
                        return
                    direction = "BUY" if ind['ema20_m15'] > ind['ema50_m15'] else "SELL"
                else:
                    # Range Mode Scout (Mean Reversion)
                    # Don't require ADX>18, we want chopped markets.
                    curr = ind.get('curr_price', 0.0)
                    bb_up = ind.get('bb_upper', 0.0)
                    bb_low = ind.get('bb_lower', 0.0)
                    rsi = ind.get('rsi', 50.0)
                    if curr <= bb_low + (bb_up - bb_low) * 0.1 and rsi < 45:
                        direction = "BUY"
                    elif curr >= bb_up - (bb_up - bb_low) * 0.1 and rsi > 55:
                        direction = "SELL"
                    else:
                        return # No range extremes met
                    
                conv = await self._calculate_conviction(direction, chop_score)
                if conv < 40.0:
                    return
                    
                cycle_id = int(time.time())
                logger.info(f"SCOUT ENTRY: {direction}. Initializing Cycle {cycle_id} with Conviction: {conv}")
                sig = SignalEvent(event.symbol, direction, self.strategy_id, event.bid, conviction=conv, volume=0.10, cycle_id=cycle_id, order_type="PROBE")'''

content = content.replace(scout_old, scout_new)

with open('src/strategy/alpha_harvester.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Replacement complete.")
