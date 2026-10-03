import sqlite3
import pandas as pd
from datetime import datetime
import json
import re

print('--- 1. MT5 Trade History (From SQLite) ---')
try:
    conn = sqlite3.connect('ledger_8000.db')
    df = pd.read_sql_query('SELECT * FROM trades', conn)
    if not df.empty:
        # Assuming there is a timestamp or close time, sort by it
        print(df.to_string())
    else:
        print('No trades found in SQLite database.')
    conn.close()
except Exception as e:
    print(f'Error reading SQLite DB: {e}')

def grep_log(file_path, patterns):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                for p in patterns:
                    if p.lower() in line.lower():
                        print(line.strip())
                        break
    except Exception as e:
        print(f'Error reading {file_path}: {e}')

print('\n--- 2. Execution & Sentinel Layer Logs ---')
print('>> execution_bridge.log:')
grep_log('logs/execution_bridge.log', ['SHIELD BLOCK', 'DOOMSDAY SHIELD', 'MARGIN_SHIELD_ERROR', 'SPREAD_SHIELD_ERROR', 'Error'])
print('\n>> tick_sentinel.log:')
grep_log('logs/tick_sentinel.log', ['Tier 1 Ultra-Fast', 'API Spam Protection'])

print('\n--- 3. Alpha Harvester & Bayesian Layer Logs ---')
print('>> alpha_harvester.log:')
grep_log('logs/alpha_harvester.log', ['BLOCK: Signal generated', 'Sentinel: Momentum ตายสนิท', 'Adaptive Correction', 'SCRATCH'])

