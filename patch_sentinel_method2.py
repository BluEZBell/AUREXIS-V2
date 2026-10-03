import re

with open('src/execution/sentinel.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("TargetHitEvent(cycle.cycle_id)", "TargetHitEvent(cycle.cycle_id, cycle.cycle_pnl)")

with open('src/execution/sentinel.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed TargetHitEvent")
