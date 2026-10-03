import os
import re

def update_harvester():
    file_path = 'src/strategy/alpha_harvester.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace the memory dictionary access with DB method
    content = content.replace(
        '''active_cycles = list(self.campaign_ledger.active_cycles.values())''',
        '''active_cycles = await self.campaign_ledger.get_active_cycles()'''
    )

    # Inject defensive try-except around the DB call if necessary,
    # but process_tick already has a massive try/except around the body.
    # Let's just ensure we return early if it fails inside process_tick.
    target_try = '''        try:
            self._last_tick_eval = current_time'''
            
    replace_try = '''        try:
            self._last_tick_eval = current_time
            try:
                # Pre-fetch active cycles from DB for this tick evaluation
                db_active_cycles = await self.campaign_ledger.get_active_cycles()
            except Exception as db_err:
                logger.error(f"Harvester Tick Error: Failed to retrieve State Ledger. {db_err}")
                await asyncio.sleep(1.0)
                return'''
                
    if target_try in content:
        content = content.replace(target_try, replace_try)
        content = content.replace('''active_cycles = await self.campaign_ledger.get_active_cycles()''', '''active_cycles = db_active_cycles''')

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("? Updated alpha_harvester.py")

if __name__ == '__main__':
    update_harvester()
