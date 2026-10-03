import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"c:\Users\bluzp\AUREXISV2\src"
filepath = os.path.join(base_dir, 'execution/sentinel.py')

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("profit_points >= 210.0", "profit_points >= 250.0")
content = content.replace("current_price - (135.0 * point)", "current_price - (150.0 * point)")
content = content.replace("current_price + (135.0 * point)", "current_price + (150.0 * point)")

content = content.replace("profit_points >= 100.0", "profit_points >= 150.0")
content = content.replace("pos.price_open + (15.0 * point)", "pos.price_open + (20.0 * point)")
content = content.replace("pos.price_open - (15.0 * point)", "pos.price_open - (20.0 * point)")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("✅ SENTINEL UPDATED")
