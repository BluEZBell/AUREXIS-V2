import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta, timezone
import os

if not mt5.initialize():
    print("MT5 initialization failed")
    quit()

# 1. MT5 Trade History
print("=== 1. MT5 Trade History ===")
now = datetime.now(timezone.utc)
from_date = now - timedelta(days=1)
deals = mt5.history_deals_get(from_date, now)
if deals is None or len(deals) == 0:
    print("No deals found in the last 24 hours.")
else:
    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    df['time'] = pd.to_datetime(df['time'], unit='s')
    # Filter only actual trades (entry/exit)
    trades = df[df['entry'].isin([0, 1])]
    if not trades.empty:
        print(trades[['ticket', 'type', 'volume', 'time', 'price', 'profit', 'commission', 'entry']].to_string())
        
        # Calculate max drawdown & consecutive losses
        profits = trades[trades['entry'] == 1]['profit'].tolist()
        balance = 100.0
        peak = balance
        max_dd = 0.0
        cons_losses = 0
        max_cons_losses = 0
        
        for pnl in profits:
            balance += pnl
            if balance > peak:
                peak = balance
            dd = (peak - balance) / peak * 100.0
            if dd > max_dd: max_dd = dd
            
            if pnl < 0:
                cons_losses += 1
                if cons_losses > max_cons_losses: max_cons_losses = cons_losses
            else:
                cons_losses = 0
        print(f"\nMax Drawdown: {max_dd:.2f}%")
        print(f"Max Consecutive Losses: {max_cons_losses}")
    else:
        print("No actual trades found.")

mt5.shutdown()

# 2. & 3. Log Parsing
import re
import sys
# enforce utf8 for printing
sys.stdout.reconfigure(encoding='utf-8')

def grep_log(filepath, keywords, context_lines=0):
    print(f"\n>> {filepath}:")
    if not os.path.exists(filepath):
        print("File not found.")
        return
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        for k in keywords:
            if k.lower() in line.lower():
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                for j in range(start, end):
                    print(lines[j].strip())
                if context_lines > 0: print("---")
                break

print("\n=== 2. Execution & Sentinel Layer Logs ===")
grep_log("logs/execution_bridge.log", ["SHIELD BLOCK", "DOOMSDAY SHIELD", "MARGIN_SHIELD_ERROR", "SPREAD_SHIELD_ERROR", "Error"])
grep_log("logs/tick_sentinel.log", ["Tier 1 Ultra-Fast", "API Spam Protection"])

print("\n=== 3. Alpha Harvester & Bayesian Layer Logs ===")
grep_log("logs/alpha_harvester.log", ["BLOCK: Signal generated", "Momentum ตายสนิท", "Adaptive Correction", "SCRATCH"])

