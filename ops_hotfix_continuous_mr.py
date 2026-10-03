import os

def hotfix_continuous_mr():
    file_path = 'src/strategy/alpha_harvester.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''        # --- REGIME SWITCH LAYER ---
        if adx_m15 < 22.0:
            if direction == "BUY":
                if curr_price <= bb_lower:
                    return 85.0
            else: # SELL
                if curr_price >= bb_upper:
                    return 85.0
            return 0.0
        # ---------------------------'''
    
    replace = '''        # --- DYNAMIC REGIME SWITCH LAYER (MEAN-REV) ---
        if adx_m15 < 22.0:
            if direction == "BUY":
                # Buy when price is below the mean (negative Z-Score)
                mr_score = 40.0 + (abs(z_score) * 20.0) if z_score < 0 else 0.0
                return min(100.0, max(0.0, mr_score))
            else: # SELL
                # Sell when price is above the mean (positive Z-Score)
                mr_score = 40.0 + (z_score * 20.0) if z_score > 0 else 0.0
                return min(100.0, max(0.0, mr_score))
        # ----------------------------------------------'''

    if target in content:
        content = content.replace(target, replace)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? Patch applied successfully: Replaced rigid MR block with Continuous Z-Score Scaling.")
    else:
        print("?? Patch skipped: Target string not found.")

if __name__ == '__main__':
    hotfix_continuous_mr()
