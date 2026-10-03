import os

def hotfix_ghost_ledger():
    file_path = 'src/core/campaign_ledger.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''                            await db.commit()
                    break'''
                    
    replace = '''                            await db.commit()
                    break
        elif event.status in ["REJECTED", "FAILED", "CANCELLED"]:
            if event.cycle_id in self.active_cycles:
                del self.active_cycles[event.cycle_id]
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("DELETE FROM cycles WHERE cycle_id=?", (event.cycle_id,))
                    await db.execute("DELETE FROM cycle_sets WHERE cycle_id=?", (event.cycle_id,))
                    await db.execute("DELETE FROM dispatched_events WHERE cycle_id=?", (event.cycle_id,))
                    await db.commit()
                logger.warning(f"Cycle {event.cycle_id} purged from Ledger due to REJECTED/FAILED order.")'''

    if target in content:
        content = content.replace(target, replace)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? Hotfix applied to campaign_ledger.py")
    else:
        print("?? Target string not found in campaign_ledger.py")

if __name__ == '__main__':
    hotfix_ghost_ledger()
