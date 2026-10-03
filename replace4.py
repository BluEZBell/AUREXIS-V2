import re

with open('src/strategy/alpha_harvester.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace in handle_scout_success
success_old = r'''        p_dir = cycle.direction
        score = 0
        if p_dir == "BUY":
            if ind['ema20_m15'] > ind['ema50_m15']: score += 1
            if ind['rsi'] > 55: score += 1
            if ind['bull_break']: score += 1
        else:
            if ind['ema20_m15'] < ind['ema50_m15']: score += 1
            if ind['rsi'] < 45: score += 1
            if ind['bear_break']: score += 1
            
        if ind['adx'] >= 22: score += 1
        
        if score >= 3:
            conviction_score = await self._calculate_conviction(p_dir)'''

success_new = r'''        p_dir = cycle.direction
        chop_score = await self.calculate_chop_score(ind)
        conviction_score = await self._calculate_conviction(p_dir, chop_score)
        
        if conviction_score >= 50.0:'''

content = content.replace(success_old, success_new)

# Note: logger.info string uses {score}, which no longer exists.
# We must also replace the logger info line.
success_log_old = r'''logger.info(f"Harvester: Scout Success Score {score}. Conviction: {conviction_score}. ML Prob: {prob:.2f}. Transitioning to SWARM_FOLLOW.")'''
success_log_new = r'''logger.info(f"Harvester: Scout Success. Conviction: {conviction_score}. ML Prob: {prob:.2f}. Transitioning to SWARM_FOLLOW.")'''
content = content.replace(success_log_old, success_log_new)

# Remove "else" fallback block in success
success_else_old = r'''        else:
            logger.info(f"Harvester: Scout Success Score {score} too low. Reverting to SCOUT_ACTIVE.")
            cycle.state = "SCOUT_ACTIVE"
            cycle.dispatched_events.discard("SCOUT_SUCCESS") # Allow retry
            await self.campaign_ledger.save_cycle(cycle)'''

success_else_new = r'''        else:
            logger.info(f"Harvester: Conviction {conviction_score} too low for SET escalation. Reverting to SCOUT_ACTIVE.")
            cycle.state = "SCOUT_ACTIVE"
            cycle.dispatched_events.discard("SCOUT_SUCCESS") # Allow retry
            await self.campaign_ledger.save_cycle(cycle)'''

content = content.replace(success_else_old, success_else_new)

# Replace in handle_scout_fail
fail_old = r'''        opp_dir = "SELL" if cycle.direction == "BUY" else "BUY"
        score = 0
        if opp_dir == "BUY":
            if ind['bull_break']: score += 1
            if ind['rsi'] > 50: score += 1
        else:
            if ind['bear_break']: score += 1
            if ind['rsi'] < 50: score += 1
            
        if ind['adx'] >= 22: score += 1
        
        if score >= 2:
            conviction_score = await self._calculate_conviction(opp_dir, chop_score=0)'''

fail_new = r'''        opp_dir = "SELL" if cycle.direction == "BUY" else "BUY"
        chop_score = await self.calculate_chop_score(ind)
        conviction_score = await self._calculate_conviction(opp_dir, chop_score)
        
        if conviction_score >= 50.0:'''

content = content.replace(fail_old, fail_new)

fail_log_old = r'''logger.info(f"Harvester: Reverse Confirmed Score {score}. Conviction: {conviction_score}. ML Prob: {prob:.2f}. Closing old cycle and Chaining new PROBE.")'''
fail_log_new = r'''logger.info(f"Harvester: Reverse Confirmed. Conviction: {conviction_score}. ML Prob: {prob:.2f}. Closing old cycle and Chaining new PROBE.")'''
content = content.replace(fail_log_old, fail_log_new)

fail_else_old = r'''        else:
            logger.info(f"Harvester: Reverse Score {score} too low. Reverting to SCOUT_ACTIVE.")
            cycle.state = "SCOUT_ACTIVE"
            cycle.dispatched_events.discard("SCOUT_FAIL")
            await self.campaign_ledger.save_cycle(cycle)'''

fail_else_new = r'''        else:
            logger.info(f"Harvester: Reverse Conviction {conviction_score} too low. Reverting to SCOUT_ACTIVE.")
            cycle.state = "SCOUT_ACTIVE"
            cycle.dispatched_events.discard("SCOUT_FAIL")
            await self.campaign_ledger.save_cycle(cycle)'''

content = content.replace(fail_else_old, fail_else_new)

with open('src/strategy/alpha_harvester.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Escalation logic replaced.")
