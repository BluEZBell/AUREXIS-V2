import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"c:\Users\bluzp\AUREXISV2\src"
filepath = os.path.join(base_dir, 'strategy/alpha_harvester.py')

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("loss_streak >= 3", "loss_streak >= 5")
content = content.replace("3 losses in a row", "5 losses in a row")
content = content.replace("total_profit >= 5.0", "total_profit >= 15.0")
content = content.replace("m15_adx < 22.0", "m15_adx < 25.0")
content = content.replace("หมดแรงดัน เก็บกำไรเข้าพอร์ต", "หมดแรงดัน เก็บกำไรเข้าพอร์ต (+)")
content = content.replace("buy_threshold = 75.0", "buy_threshold = 70.0")
content = content.replace("sell_threshold = 25.0", "sell_threshold = 30.0")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("✅ ALPHA HARVESTER UPDATED")
