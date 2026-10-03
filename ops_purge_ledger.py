import asyncio
import os
import sys
import aiosqlite

async def purge_ledger():
    db_dir = "db"
    db_path = os.path.join(db_dir, "aurexis_ledger.db")
    
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

    print("=" * 60)
    print(">>> AUREXIS V2: CLEAN SLATE PROTOCOL <<<")
    print("=" * 60)
    
    try:
        async with aiosqlite.connect(db_path) as db:
            # Drop existing tables
            print("[INFO] Dropping existing tracking tables...")
            await db.execute("DROP TABLE IF EXISTS cycles")
            await db.execute("DROP TABLE IF EXISTS cycle_sets")
            await db.execute("DROP TABLE IF EXISTS dispatched_events")
            
            # Re-initialize pristine tables
            print("[INFO] Re-initializing pristine tables...")
            await db.execute("PRAGMA journal_mode=WAL;")
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cycles (
                    cycle_id INTEGER PRIMARY KEY,
                    direction TEXT,
                    state TEXT,
                    probe_ticket INTEGER,
                    cycle_pnl REAL,
                    realized_pnl REAL,
                    updated_at REAL
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cycle_sets (
                    cycle_id INTEGER,
                    ticket INTEGER,
                    PRIMARY KEY (cycle_id, ticket)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS dispatched_events (
                    cycle_id INTEGER,
                    event_name TEXT,
                    PRIMARY KEY (cycle_id, event_name)
                )
            """)
            
            await db.commit()
            print("[CRITICAL] Campaign Ledger PURGED. System is a Clean Slate. Ready for LIVE EXECUTION.")
            print("=" * 60)
            
    except Exception as e:
        print(f"[FAIL] Error during ledger purge: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(purge_ledger())
