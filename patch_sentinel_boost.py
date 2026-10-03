import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"c:\Users\bluzp\AUREXISV2\src"
filepath = os.path.join(base_dir, 'execution/sentinel.py')

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

bad_str = '''            # Tier 2 (Cash Lock)
            elif profit_points >= 210.0:
                trail_sl = current_price - (135.0 * point) if direction == "BUY" else current_price + (135.0 * point)
                if pos.sl == 0.0 or (direction == "BUY" and trail_sl > pos.sl + (15.0 * point)) or (direction == "SELL" and trail_sl < pos.sl - (15.0 * point)):
                    new_sl = trail_sl
                    reason = "Tier 2 Trailing"
                    
            # 🚀 [ANTIGRAVITY] Tier 1 (Ultra-Fast Break-Even)
            elif profit_points >= 100.0:
                true_be = self.risk_manager.calculate_true_breakeven(symbol_info, pos.price_open, direction)
                if direction == "BUY":
                    true_be = max(true_be, pos.price_open + (15.0 * point))
                    true_be = min(true_be, current_price - max(70.0, stops_level / point) * point)
                else:
                    true_be = min(true_be, pos.price_open - (15.0 * point))
                    true_be = max(true_be, current_price + max(70.0, stops_level / point) * point)'''

good_str = '''            # Tier 2 (Cash Lock)
            elif profit_points >= 250.0:
                trail_sl = current_price - (150.0 * point) if direction == "BUY" else current_price + (150.0 * point)
                if pos.sl == 0.0 or (direction == "BUY" and trail_sl > pos.sl + (15.0 * point)) or (direction == "SELL" and trail_sl < pos.sl - (15.0 * point)):
                    new_sl = trail_sl
                    reason = "Tier 2 Trailing"
                    
            # 🚀 [ANTIGRAVITY] Tier 1 (Ultra-Fast Break-Even)
            elif profit_points >= 150.0:
                true_be = self.risk_manager.calculate_true_breakeven(symbol_info, pos.price_open, direction)
                if direction == "BUY":
                    true_be = max(true_be, pos.price_open + (20.0 * point))
                    true_be = min(true_be, current_price - max(70.0, stops_level / point) * point)
                else:
                    true_be = min(true_be, pos.price_open - (20.0 * point))
                    true_be = max(true_be, current_price + max(70.0, stops_level / point) * point)'''

if bad_str in content:
    content = content.replace(bad_str, good_str)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ SENTINEL UPDATED")
else:
    print("❌ PATTERNS NOT FOUND IN SENTINEL")
