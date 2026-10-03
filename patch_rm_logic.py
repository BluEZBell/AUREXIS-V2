import re

with open('src/execution/risk_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''            conviction_multiplier = min(1.0, conviction / 85.0) if conviction > 0 else 0.0
            allocated_risk_money = available_risk_money * conviction_multiplier
            
            raw_lot = allocated_risk_money / (strict_sl_points * point_value) if (strict_sl_points * point_value) > 0 else 0.0'''

replacement = '''            conviction_multiplier = min(1.0, conviction / 85.0) if conviction > 0 else 0.0
            allocated_risk_money = available_risk_money * conviction_multiplier
            
            # Operation: Convex Risk Allocation & Hyper-Scaling
            if is_hyper_scale:
                allocated_risk_money *= 2.0
                logger.info("HYPER-SCALE: Applied 2.0x asymmetric multiplier to base risk allocation.")
            
            raw_lot = allocated_risk_money / (strict_sl_points * point_value) if (strict_sl_points * point_value) > 0 else 0.0'''

if target in content:
    content = content.replace(target, replacement)
    with open('src/execution/risk_manager.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched risk allocation logic")
else:
    print("Target not found.")

