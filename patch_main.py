import re

with open('src/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_call = '''    campaign_ledger = CampaignLedger(event_bus)
    await campaign_ledger.initialize()
    await campaign_ledger.load_and_reconcile()'''

new_call = '''    campaign_ledger = CampaignLedger(event_bus)
    await campaign_ledger.initialize()
    await campaign_ledger.load_and_reconcile()
    campaign_ledger.start_realtime_reconciliation()'''

content = content.replace(old_call, new_call)

with open('src/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
