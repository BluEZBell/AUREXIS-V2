import os
import shutil
import asyncio
from datetime import datetime

DB_DIR = "db"
BACKUP_DIR = os.path.join(DB_DIR, "backups")
LEDGER_DB = os.path.join(DB_DIR, "aurexis_ledger.db")
LEDGER_WAL = os.path.join(DB_DIR, "aurexis_ledger.db-wal")
LEDGER_SHM = os.path.join(DB_DIR, "aurexis_ledger.db-shm")

async def backup_ledger():
    print("=" * 60)
    print(">>> AUREXIS V2: DATA LAKE BACKUP UTILITY <<<")
    print("=" * 60)
    
    if not os.path.exists(LEDGER_DB):
        print("[!] ERROR: Ledger database not found at", LEDGER_DB)
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d")
    backup_db_path = os.path.join(BACKUP_DIR, f"aurexis_ledger_{timestamp}.db")
    backup_wal_path = os.path.join(BACKUP_DIR, f"aurexis_ledger_{timestamp}.db-wal")
    backup_shm_path = os.path.join(BACKUP_DIR, f"aurexis_ledger_{timestamp}.db-shm")

    print("[*] Initiating secure asynchronous copy...")
    
    # We use asyncio.to_thread for disk I/O to maintain the async standard of the project
    await asyncio.to_thread(shutil.copy2, LEDGER_DB, backup_db_path)
    print(f"[SUCCESS] Ledger DB copied to: {backup_db_path}")

    if os.path.exists(LEDGER_WAL):
        await asyncio.to_thread(shutil.copy2, LEDGER_WAL, backup_wal_path)
        print(f"[SUCCESS] WAL File copied to: {backup_wal_path}")
        
    if os.path.exists(LEDGER_SHM):
        await asyncio.to_thread(shutil.copy2, LEDGER_SHM, backup_shm_path)
        print(f"[SUCCESS] SHM File copied to: {backup_shm_path}")
        
    print("=" * 60)
    print("[OK] DATA LAKE SECURED. READY FOR EOD ANALYTICS.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(backup_ledger())
