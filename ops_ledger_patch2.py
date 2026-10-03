import os

def fix_get_active_cycles():
    file_path = 'src/core/campaign_ledger.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''                c = CampaignCycle(
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
                )'''
                
    replace = '''                c = CampaignCycle(
                    cycle_id=row["cycle_id"],
                    direction=row["direction"],
                    state=row["state"],
                    probe_ticket=row["probe_ticket"],
                    cycle_pnl=row["cycle_pnl"],
                    realized_pnl=row["realized_pnl"],
                    updated_at=row["updated_at"],
                    mfe=row["mfe"],
                    chop_score=row["chop_score"],
                    recovery_start_time=row["recovery_start_time"]
                )'''

    if target in content:
        content = content.replace(target, replace)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? Fixed get_active_cycles KeyError in campaign_ledger.py")
    else:
        print("?? Target not found.")

if __name__ == '__main__':
    fix_get_active_cycles()
