import os

def implement_get_active_cycles():
    file_path = 'src/core/campaign_ledger.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''    async def close_cycle(self, cycle_id: int):'''
                    
    replace = '''    async def get_active_cycles(self) -> list:
        # Returns a strongly-typed collection of active cycles from SQLite DB to prevent memory mismatch
        cycles = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM cycles")
            rows = await cursor.fetchall()
            for row in rows:
                c = CampaignCycle(
                    cycle_id=row["cycle_id"],
                    direction=row["direction"],
                    state=row["state"],
                    probe_ticket=row["probe_ticket"],
                    cycle_pnl=row["cycle_pnl"],
                    realized_pnl=row["realized_pnl"],
                    timestamp_open=row["timestamp_open"],
                    updated_at=row["updated_at"],
                    mfe=row["mfe"],
                    chop_score=row["chop_score"],
                    recovery_start_time=row["recovery_start_time"]
                )
                
                c_cursor = await db.execute("SELECT ticket FROM cycle_sets WHERE cycle_id=?", (c.cycle_id,))
                c_rows = await c_cursor.fetchall()
                c.set_tickets = [r["ticket"] for r in c_rows]
                
                cycles.append(c)
        return cycles

    async def close_cycle(self, cycle_id: int):'''

    if target in content:
        content = content.replace(target, replace)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? Added get_active_cycles to campaign_ledger.py")
    else:
        print("?? Target string not found in campaign_ledger.py")

if __name__ == '__main__':
    implement_get_active_cycles()
