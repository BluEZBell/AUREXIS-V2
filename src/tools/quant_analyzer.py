import sqlite3
import pandas as pd
import os

def generate_tearsheet():
    # Locate ledger
    db_paths = ['ledger_8000.db', '../ledger_8000.db', '../../ledger_8000.db', 'db/ledger_8000.db', 'logs/ledger_8000.db']
    db_path = None
    for p in db_paths:
        if os.path.exists(p):
            db_path = p
            break
            
    if not db_path:
        print("ERROR: ledger_8000.db not found.")
        return

    print(f"[*] Connecting to {db_path} in READ-ONLY mode...")
    uri = f"file:{os.path.abspath(db_path)}?mode=ro"
    
    try:
        conn = sqlite3.connect(uri, uri=True)
        query = "SELECT * FROM active_trades WHERE status LIKE 'CLOSED%'"
        df = pd.read_sql_query(query, conn)
        conn.close()
    except Exception as e:
        print(f"Failed to query database: {e}")
        return

    if df.empty:
        print("[-] No historical trades found in the ledger.")
        return

    print("[*] Extracting and calculating metrics...")

    # Infer PnL
    df['PnL'] = df['price'].apply(lambda x: x if abs(x) < 1000 else 0.0)
    
    # Calculate Inferred MFE and MAE
    df['MFE'] = df['PnL'].apply(lambda x: x if x > 0 else 0.0)
    df['MAE'] = df['PnL'].apply(lambda x: abs(x) if x < 0 else 0.0)
    
    # Attempt to fetch MT5 comments to identify Harvester vs Runner (since AUREXIS truncates to 12 chars: 'AUREXIS_HARV')
    try:
        import MetaTrader5 as mt5
        from datetime import datetime
        if mt5.initialize():
            deals = mt5.history_deals_get(datetime(2020, 1, 1), datetime.now())
            if deals:
                deals_df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
                deals_df = deals_df[['order', 'comment']]
                df = df.merge(deals_df, left_on='identifier', right_on='order', how='left')
                df['strategy_id'] = df['comment'].fillna('UNKNOWN')
            mt5.shutdown()
    except Exception:
        pass
        
    if 'strategy_id' not in df.columns:
        df['strategy_id'] = 'UNKNOWN'

    df['Ticket_Type'] = 'Standard'
    df.loc[df['strategy_id'].str.contains('HARV', case=False, na=False), 'Ticket_Type'] = 'Harvester'
    df.loc[df['strategy_id'].str.contains('RUNN', case=False, na=False), 'Ticket_Type'] = 'Runner'

    # Metrics
    total_trades = len(df)
    winning_trades = len(df[df['PnL'] > 0])
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0.0
    
    avg_mfe = df['MFE'].mean()
    avg_mae = df['MAE'].mean()
    max_mae = df['MAE'].max()
    
    avg_win = df[df['PnL'] > 0]['PnL'].mean() if winning_trades > 0 else 0.0
    avg_loss = df[df['PnL'] < 0]['PnL'].mean() if (total_trades - winning_trades) > 0 else 0.0
    rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0

    print("="*60)
    print(" ?? AUREXIS V2 POST-TRADE QUANTITATIVE TEARSHEET ?? ")
    print("="*60)
    print(f" Total Trades Analyzed: {total_trades}")
    print(f" Overall Win Rate:      {win_rate:.2f}%")
    print(f" Average R:R Ratio:     {rr_ratio:.2f}")
    print("-" * 60)
    print(f" Average MFE (Inferred): +{avg_mfe:.2f} USD")
    print(f" Average MAE (Inferred): -{avg_mae:.2f} USD")
    print(f" Maximum MAE Encountered: -{max_mae:.2f} USD")
    print("-" * 60)
    
    print(" ?? TWIN-TICKET PERFORMANCE: ")
    for ttype in ['Harvester', 'Runner', 'Standard']:
        tdf = df[df['Ticket_Type'] == ttype]
        if len(tdf) > 0:
            t_win = len(tdf[tdf['PnL'] > 0])
            t_wr = (t_win / len(tdf)) * 100
            t_pnl = tdf['PnL'].sum()
            print(f"   - {ttype}: {len(tdf)} trades | Win Rate: {t_wr:.1f}% | Net PnL: {t_pnl:.2f}")

    print("="*60)
    print(" ?? ACTIONABLE INSIGHTS:")
    if avg_mae > 0:
        if avg_mae > 1.5:
            print(f"   [!] Average MAE is relatively high ({avg_mae:.2f}). Consider tightening Minimum SL or improving entries.")
        else:
            print(f"   [+] Average MAE is well-controlled ({avg_mae:.2f}). The current 200-point structural floor is effective.")
    if avg_mfe > abs(avg_loss) * 2:
        print(f"   [+] MFE shows strong upside potential. Runners are capturing good excursion.")
    elif avg_mfe > 0 and avg_mfe < abs(avg_loss):
        print(f"   [-] Trades are failing to reach favorable excursions. Sentinel may be exiting too late or entries are poor.")
    print("="*60)

if __name__ == '__main__':
    generate_tearsheet()
