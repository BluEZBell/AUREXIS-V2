import re

with open('run_live.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_call = '''        await self.bridge.initialize()
        
        # MT5 is initialized, now safe to reconcile campaign ledger
        await self.campaign_ledger.load_and_reconcile()'''

new_call = '''        await self.bridge.initialize()
        
        # MT5 is initialized, now safe to reconcile campaign ledger
        await self.campaign_ledger.load_and_reconcile()
        self.campaign_ledger.start_realtime_reconciliation()'''

content = content.replace(old_call, new_call)

with open('run_live.py', 'w', encoding='utf-8') as f:
    f.write(content)
