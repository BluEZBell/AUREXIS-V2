import re

with open('src/strategy/alpha_harvester.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the Scout Entry logic block inside process_tick
scout_entry_old = r'''            # Global CHOP_LOCK Check
            if len(active_cycles) == 0 and self.auto_sniper:
                if await self.check_whipsaw_lock(ind):
                    return
                    
                if chop_score >= 4:
                    logger.debug(f"CHOP_LOCK active (Score: {chop_score}). Waiting for Breakout.")
                    return
                    
                if chop_score >= 3 and breakout_score < 4:
                    return # Wait for clear breakout
                    
                # SCOUT Entry Logic
                if ind['adx'] < 18 or (48 <= ind['rsi'] <= 52):
                    return
                
                direction = "BUY" if ind['ema20_m15'] > ind['ema50_m15'] and ind['rsi'] > 55 else "SELL"
                if direction == "SELL" and not (ind['ema20_m15'] < ind['ema50_m15'] and ind['rsi'] < 45):
                    return'''

scout_entry_new = r'''            # Global Entry Check
            if len(active_cycles) == 0 and self.auto_sniper:
                if await self.check_whipsaw_lock(ind):
                    return
                    
                # SCOUT Entry Logic (Forked for Trend vs Range)
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
                        return # No range extremes met'''

content = content.replace(scout_entry_old, scout_entry_new)

# Remove cycle.state chop_score blocks
cycle_chop_old = r'''                    if chop_score >= 4 and cycle.state not in ["CHOP_LOCK", "WAIT", "CLOSE_RECOVERY"]:
                        logger.warning(f"Cycle {cycle.cycle_id}: Chop Score {chop_score}. Entering CHOP_LOCK.")
                        cycle.state = "CHOP_LOCK"
                        await self.campaign_ledger.save_cycle(cycle)
                        continue
                        
                    if chop_score == 3 and cycle.state not in ["CHOP_WARNING", "CHOP_LOCK", "WAIT", "CLOSE_RECOVERY"]:
                        logger.warning(f"Cycle {cycle.cycle_id}: Chop Score 3. Entering CHOP_WARNING.")
                        cycle.state = "CHOP_WARNING"
                        await self.campaign_ledger.save_cycle(cycle)
                        continue
                        
                    if cycle.state in ["CHOP_LOCK", "CHOP_WARNING"] and breakout_score >= 4:
                        logger.info(f"Cycle {cycle.cycle_id}: Breakout Score {breakout_score}. Resuming SWARM_FOLLOW.")
                        cycle.state = "SWARM_FOLLOW"
                        await self.campaign_ledger.save_cycle(cycle)
                        

                        '''
content = content.replace(cycle_chop_old, "")

with open('src/strategy/alpha_harvester.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Replaced process_tick chop_score logic.")
