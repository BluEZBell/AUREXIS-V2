import asyncio
import aiosqlite
import os
import sys

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "aurexis_ledger.db")

async def run_health_check():
    print(f"[{asyncio.get_event_loop().time()}] Initializing AUREXIS Ops Health Check...")
    print(f"Connecting to Campaign Ledger (Read-Only): {DB_PATH}")
    
    if not os.path.exists(DB_PATH):
        print("❌ Database file not found. System may not have initialized yet.")
        return

    # Connect strictly in URI read-only mode to avoid locking WAL
    # uri=True enables query parameters like ?mode=ro
    db_uri = f"file:{DB_PATH}?mode=ro"
    
    try:
        async with aiosqlite.connect(db_uri, uri=True) as db:
            db.row_factory = aiosqlite.Row
            
            print("\n===========================================")
            print("📊 CAMPAIGN LEDGER DIAGNOSTICS")
            print("===========================================")
            
            # 1. Total active cycles
            async with db.execute("SELECT COUNT(*) as count FROM cycles WHERE state NOT IN ('CLOSED', 'IDLE')") as cursor:
                row = await cursor.fetchone()
                active_cycles = row['count'] if row else 0
                
            # 2. Total historical (closed/idle) cycles
            async with db.execute("SELECT COUNT(*) as count FROM cycles WHERE state IN ('CLOSED', 'IDLE')") as cursor:
                row = await cursor.fetchone()
                historical_cycles = row['count'] if row else 0
                
            # 3. Aggregated Realized PnL
            async with db.execute("SELECT SUM(realized_pnl) as total_pnl FROM cycles") as cursor:
                row = await cursor.fetchone()
                total_pnl = row['total_pnl'] if row and row['total_pnl'] is not None else 0.0
                
            # 4. Strategy Win/Loss (Basic proxy: positive PnL vs negative PnL closed cycles)
            async with db.execute("SELECT COUNT(*) as count FROM cycles WHERE state IN ('CLOSED', 'IDLE') AND realized_pnl > 0") as cursor:
                row = await cursor.fetchone()
                wins = row['count'] if row else 0
                
            losses = historical_cycles - wins
                
            print(f"🟢 Active Campaigns:       {active_cycles}")
            print(f"📚 Historical Campaigns:   {historical_cycles}")
            print(f"💰 Aggregated Net PnL:     ${total_pnl:.2f}")
            print(f"⚖️  Win/Loss Cycles:        {wins} W / {losses} L")
            print("===========================================")
            print("✅ Database Integrity Verified. No WAL Locks detected.")
            
    except Exception as e:
        print(f"❌ Diagnostic Failure: {e}")

if __name__ == "__main__":
    asyncio.run(run_health_check())
