import os
import re

def refactor_harvester():
    file_path = 'src/strategy/alpha_harvester.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Inject self.scorer in __init__
    if "self.scorer = AlphaScorer()" not in content:
        init_target = '''        from src.analytics.ml_oracle import MLOracle
        self.oracle = MLOracle()'''
        init_replace = '''        from src.analytics.ml_oracle import MLOracle
        self.oracle = MLOracle()
        
        from src.alpha.alpha_scorer import AlphaScorer
        self.scorer = AlphaScorer()'''
        content = content.replace(init_target, init_replace)

    # 2. Refactor process_tick
    # We will locate the 'active_cycles = await self.campaign_ledger.get_active_cycles()' inside process_tick
    # and replace everything until 'from src.core.event_bus import StrategyStateEvent'
    
    match = re.search(r'(active_cycles = await self\.campaign_ledger\.get_active_cycles\(\)\s+)(if len\(active_cycles\) == 0 and self\.auto_sniper:.*?)(\s+from src\.core\.event_bus import StrategyStateEvent)', content, flags=re.DOTALL)
    
    if match:
        prefix = match.group(1)
        old_logic = match.group(2)
        suffix = match.group(3)
        
        # We need to extract the existing 'for cycle in active_cycles:' logic from old_logic, because we don't want to destroy the HOLD_RECOVERY and old SWARM logics.
        # Actually, let's just use regex to extract the inner of else:\n                for cycle in active_cycles:
        
        for_loop_match = re.search(r'for cycle in active_cycles:(.*?)(?=\s+# Calculate Z-Score|\z)', old_logic, flags=re.DOTALL)
        if for_loop_match:
            for_loop_body = for_loop_match.group(1)
            # The for_loop_body might go too far, so let's be careful.
            pass
            
        # Instead of complex regex extraction, let's just do a string replacement on the old SCOUT ENTRY logic,
        # and then append the Gateway logic at the end of the loop.
        
        print("Using precise string replacement...")

