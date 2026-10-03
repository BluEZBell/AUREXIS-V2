import re

with open('src/execution/sentinel.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''            floor = None
            activation_tier_2 = spread_cost_usd * 10.0
            activation_tier_1 = spread_cost_usd * 3.0
            
            if new_mfe >= activation_tier_2:
                floor = new_mfe * 0.5
            elif new_mfe >= activation_tier_1:
                floor = spread_cost_usd * 1.5'''

new_block = '''            floor = None
            activation_tier_2 = spread_cost_usd * 10.0
            activation_tier_1 = spread_cost_usd * 4.0
            activation_tier_0 = spread_cost_usd * 2.0
            
            if new_mfe >= activation_tier_2:
                floor = new_mfe * 0.5  # 50% Trailing Free-Roll
            elif new_mfe >= activation_tier_1:
                floor = spread_cost_usd * 1.5  # Solid Break-Even
            elif new_mfe >= activation_tier_0:
                floor = spread_cost_usd * 0.5  # Micro-Defense (Covers basic friction, guarantees green)'''

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('src/execution/sentinel.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patch applied successfully.")
else:
    print("Old block not found!")
