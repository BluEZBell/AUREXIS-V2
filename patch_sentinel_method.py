import re

with open('src/execution/sentinel.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("self.campaign_ledger.get_active_cycles()", "list(self.campaign_ledger.active_cycles.values())")

with open('src/execution/sentinel.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed get_active_cycles")
