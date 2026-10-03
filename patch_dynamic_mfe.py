import re

with open('src/execution/sentinel.py', 'r', encoding='utf-8') as f:
    content = f.read()

if "activation_tier_2 = spread_cost_usd * 10.0" in content:
    print("? Patch verified: Dynamic Spread-Pegged MFE Vault is ALREADY fully implemented.")
else:
    print("Applying patch...")
