import os

def overclock_engine():
    # 1. Modify src/core/dynamic_params.py
    dp_path = 'src/core/dynamic_params.py'
    with open(dp_path, 'r', encoding='utf-8') as f:
        dp_content = f.read()
        
    dp_target = '''        conviction_factor = max(1.0, (150.0 - conviction_score) / 100.0)
        spacing = atr * 0.15 * conviction_factor
        
        # Hyper-Drive Compression for small accounts
        if equity < 500.0:
            spacing *= 0.5
            
        return max(spacing, 20.0)'''
        
    dp_replace = '''        conviction_factor = max(1.0, (150.0 - conviction_score) / 100.0)
        spacing = atr * 0.10 * conviction_factor
        
        # Hyper-Drive Compression for small accounts
        if equity < 500.0:
            spacing *= 0.5
            return max(spacing, 10.0)
            
        return max(spacing, 20.0)'''
        
    if dp_target in dp_content:
        dp_content = dp_content.replace(dp_target, dp_replace)
        with open(dp_path, 'w', encoding='utf-8') as f:
            f.write(dp_content)
        print("? Overclocked dynamic_params.py")
    else:
        print("?? Could not find target block in dynamic_params.py")
        
    # 2. Modify src/strategy/alpha_harvester.py
    ah_path = 'src/strategy/alpha_harvester.py'
    with open(ah_path, 'r', encoding='utf-8') as f:
        ah_content = f.read()
        
    ah_target_def = '''    async def _evaluate_free_roll(self, cycle) -> bool:
        """Monitor PnL/MFE. Once True Break-Even is cleared, set state to 'FREE_ROLL'."""
        if cycle.state not in ["SCOUT_ACTIVE", "SWARM_FOLLOW", "SWARM_REVERSE"]:
            return False
            
        target_break_even_usd = getattr(config, 'FREE_ROLL_THRESHOLD_USD', 1.0)'''
        
    ah_replace_def = '''    async def _evaluate_free_roll(self, cycle, ind: dict) -> bool:
        """Monitor PnL/MFE. Once True Break-Even is cleared, set state to 'FREE_ROLL'."""
        if cycle.state not in ["SCOUT_ACTIVE", "SWARM_FOLLOW", "SWARM_REVERSE"]:
            return False
            
        target_break_even_usd = (ind.get('spread_points', 10.0) * 0.03) + 0.10'''
        
    ah_target_call = '''                        await self._evaluate_free_roll(cycle)'''
    ah_replace_call = '''                        await self._evaluate_free_roll(cycle, ind)'''
    
    if ah_target_def in ah_content and ah_target_call in ah_content:
        ah_content = ah_content.replace(ah_target_def, ah_replace_def)
        ah_content = ah_content.replace(ah_target_call, ah_replace_call)
        with open(ah_path, 'w', encoding='utf-8') as f:
            f.write(ah_content)
        print("? Overclocked alpha_harvester.py")
    else:
        print("?? Could not find target blocks in alpha_harvester.py")

if __name__ == '__main__':
    overclock_engine()
