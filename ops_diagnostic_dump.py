import sqlite3
import csv
import os

def query_ledger():
    db_path = 'file:db/aurexis_ledger.db?mode=ro'
    try:
        conn = sqlite3.connect(db_path, uri=True)
        cursor = conn.cursor()
        
        # Check columns dynamically as mfe, chop_score, recovery_start_time were recently added
        columns_info = [col[1] for col in conn.execute('PRAGMA table_info(cycles)')]
        
        cols = ['cycle_id', 'direction', 'state', 'cycle_pnl', 'realized_pnl', 'mfe', 'chop_score', 'recovery_start_time']
        
        # Build query cols based on what actually exists to prevent crashes
        select_cols = [c if c in columns_info else "0" for c in cols]
        select_str = ", ".join(select_cols)
        
        cursor.execute(f"SELECT {select_str} FROM cycles ORDER BY cycle_id DESC LIMIT 15")
        rows = cursor.fetchall()
        
        print(f"{'ID':<6} | {'Direction':<10} | {'State':<15} | {'PnL':<8} | {'Realized':<8} | {'MFE':<8} | {'Chop':<4} | {'Recovery Start'}")
        print("-" * 90)
        for row in rows:
            pnl = f"{row[3]:.2f}"
            realized = f"{row[4]:.2f}"
            mfe = f"{row[5]:.2f}"
            chop = f"{row[6]}"
            recovery = f"{row[7]:.1f}" if row[7] else "0.0"
            print(f"{row[0]:<6} | {row[1]:<10} | {row[2]:<15} | {pnl:<8} | {realized:<8} | {mfe:<8} | {chop:<4} | {recovery}")
            
        conn.close()
    except Exception as e:
        print(f"Error reading aurexis_ledger.db: {e}")

def read_journal():
    csv_path = 'logs/institutional_journal.csv'
    if not os.path.exists(csv_path):
        print("institutional_journal.csv not found.")
        return
        
    try:
        with open(csv_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        print(f"{'Regime':<12} | {'Max Conviction':<15} | {'Realized PnL':<15} | {'Exit Reason'}")
        print("-" * 80)
        for row in rows[-15:]:
            regime = row.get('Regime_At_Entry', 'N/A')
            conviction = row.get('Max_Conviction_Score', '0')
            pnl = row.get('Total_Realized_PnL', '0')
            reason = row.get('Exit_Reason', 'N/A')
            print(f"{regime:<12} | {conviction:<15} | {pnl:<15} | {reason}")
    except Exception as e:
        print(f"Error reading journal CSV: {e}")

def query_quant_lake():
    db_path = 'file:db/aurexis_quant_lake.db?mode=ro'
    try:
        conn = sqlite3.connect(db_path, uri=True)
        cursor = conn.cursor()
        
        cursor.execute("SELECT slippage_points FROM feature_snapshots ORDER BY id DESC LIMIT 50")
        rows = cursor.fetchall()
        
        if rows:
            slippages = [r[0] for r in rows if r[0] is not None]
            if slippages:
                avg_slip = sum(slippages) / len(slippages)
                max_slip = max(slippages)
                print(f"Avg Slippage (last {len(slippages)}): {avg_slip:.2f} pts")
                print(f"Max Slippage (last {len(slippages)}): {max_slip:.2f} pts")
            else:
                print("No valid slippage data found in the last 50 snapshots.")
        else:
            print("No snapshot data available.")
            
        conn.close()
    except Exception as e:
        print(f"Error reading aurexis_quant_lake.db: {e}")

if __name__ == "__main__":
    print("==========================================================================================")
    print("                   AUREXIS V2 POST-MARKET DIAGNOSTIC DUMP                                 ")
    print("==========================================================================================\n")
    
    print(">>> 1. LEDGER CYCLES (aurexis_ledger.db - Last 15)")
    query_ledger()
    print("\n")
    
    print(">>> 2. INSTITUTIONAL JOURNAL (logs/institutional_journal.csv - Last 15)")
    read_journal()
    print("\n")
    
    print(">>> 3. EXECUTION DEGRADATION (aurexis_quant_lake.db - feature_snapshots)")
    query_quant_lake()
    print("\n==========================================================================================")
