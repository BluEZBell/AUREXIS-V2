import os

def fix_harvester():
    file_path = 'src/strategy/alpha_harvester.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''        self._last_tick_eval = current_time
        
        try:'''
        
    replace = '''        self._last_tick_eval = current_time
        
        try:
            try:
                # Pre-fetch active cycles from DB for this tick evaluation
                db_active_cycles = await self.campaign_ledger.get_active_cycles()
            except Exception as db_err:
                logger.error(f"Harvester Tick Error: 'CampaignLedger' object failed state retrieval. {db_err}")
                await asyncio.sleep(1.0)
                return'''

    if target in content:
        content = content.replace(target, replace)
        content = content.replace('active_cycles = list(self.campaign_ledger.active_cycles.values())', 'active_cycles = db_active_cycles')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? Harvester patched successfully.")
    else:
        print("?? Target not found.")

if __name__ == '__main__':
    fix_harvester()
