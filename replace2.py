import re

with open('src/strategy/alpha_harvester.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace _calculate_conviction
pattern1 = re.compile(r'    async def _calculate_conviction\(self, direction: str\) -> float:.*?(?=    async def get_indicators)', re.DOTALL)

new_logic = '''    async def _calculate_conviction(self, direction: str, chop_score: int = 0) -> float:
        score = 50.0  # Base neutral score
        
        ind = self._latest_indicators.get(config.TRADING_SYMBOL)
        if not ind:
            return 20.0
            
        curr_price = ind.get('curr_price', 0.0)
        ema20_m15 = ind.get('ema_20', 0.0)
        rsi = ind.get('rsi', 50.0)
        bb_upper = ind.get('bb_upper', 0.0)
        bb_lower = ind.get('bb_lower', 0.0)
        adx_m15 = ind.get('adx_m15', 0.0)
        macd_hist = ind.get('macd_hist', 0.0)
        
        if chop_score < 3:
            # PATH A: TREND_MODE (Springboard Sniper)
            if direction == "BUY":
                if ema20_m15 > 0 and curr_price <= ema20_m15 * 1.0005 and curr_price >= ema20_m15 * 0.9990 and 40 <= rsi <= 55:
                    score += 30.0
                if rsi > 65 or curr_price >= bb_upper - (bb_upper - bb_lower) * 0.1:
                    score -= 50.0
            else:
                if ema20_m15 > 0 and curr_price >= ema20_m15 * 0.9995 and curr_price <= ema20_m15 * 1.0010 and 45 <= rsi <= 60:
                    score += 30.0
                if rsi < 35 or curr_price <= bb_lower + (bb_upper - bb_lower) * 0.1:
                    score -= 50.0
                    
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
            # PATH B: RANGE_MODE (Mean-Reversion)
            if direction == "BUY":
                if curr_price <= bb_lower + (bb_upper - bb_lower) * 0.1 and rsi < 45:
                    score += 40.0
                if curr_price >= bb_upper - (bb_upper - bb_lower) * 0.1:
                    score -= 50.0
            else:
                if curr_price >= bb_upper - (bb_upper - bb_lower) * 0.1 and rsi > 55:
                    score += 40.0
                if curr_price <= bb_lower + (bb_upper - bb_lower) * 0.1:
                    score -= 50.0

        return max(0.0, min(100.0, score))
            
'''

content = pattern1.sub(new_logic, content)

# Remove CHOP_LOCK and CHOP_WARNING logic, and pass chop_score
content = content.replace('conv = await self._calculate_conviction(direction)', 'conv = await self._calculate_conviction(direction, chop_score)')
content = content.replace('conv = await self._calculate_conviction(cycle.direction)', 'conv = await self._calculate_conviction(cycle.direction, chop_score)')
content = content.replace('conviction_score = await self._calculate_conviction(opp_dir)', 'conviction_score = await self._calculate_conviction(opp_dir, chop_score=0)') # For scout fails we don't have chop_score in scope easily, we can default it. Wait! Better to just pass no arg for those and let default=0 handle it or pass 0.

# Replace the chop_score block and global state telemetry
chop_block = r'''            if chop_score >= 4:
                cycle_state = "CHOP_LOCK"
                # Phase 21: Broadcast warning before return
                await self.event_bus.publish(CommandEvent(action="WARNING_STOP_ADD"))
                logger.warning(f"Harvester: CHOP_LOCK (Score {chop_score}). Halting all new entries.")
                
            elif chop_score >= 3:
                cycle_state = "CHOP_WARNING"
                logger.info(f"Harvester: CHOP_WARNING (Score {chop_score}). Suspending new PROBEs.")'''

chop_replacement = r'''            cycle_state = "IDLE"'''

content = content.replace(chop_block, chop_replacement)

# Remove if cycle.state in ["CHOP_LOCK", "CHOP_WARNING"]: continue
chop_continue = r'''                    if cycle.state in ["CHOP_LOCK", "CHOP_WARNING"]:
                        continue'''
content = content.replace(chop_continue, "")

# Telemetry block update
telemetry_old = r'''            else:
                if chop_score >= 4:
                    global_state = "CHOP_LOCK"
                elif chop_score >= 3:
                    global_state = "CHOP_WARNING"'''

telemetry_new = r'''            else:
                global_state = "TREND_ACTIVE" if chop_score < 3 else "RANGE_ACTIVE"'''

content = content.replace(telemetry_old, telemetry_new)


with open('src/strategy/alpha_harvester.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Rewrite Complete.")
