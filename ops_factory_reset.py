import os
import shutil
import time
import sqlite3

def factory_reset():
    db_path = os.path.join("db", "aurexis_ledger.db")
    csv_path = os.path.join("logs", "institutional_journal.csv")
    
    timestamp = int(time.time())
    
    print("==========================================================================")
    print("                 AUREXIS V2 - FACTORY RESET PROTOCOL")
    print("==========================================================================")
    
    # Process DB
    if os.path.exists(db_path):
        db_backup = os.path.join("db", f"aurexis_ledger_backup_{timestamp}.db")
        try:
            shutil.copy2(db_path, db_backup)
            print(f"[+] BACKUP SUCCESS: {db_backup}")
            os.remove(db_path)
            print(f"[+] PURGE SUCCESS: {db_path} has been wiped.")
        except Exception as e:
            print(f"[-] ERROR processing DB: {e}")
    else:
        print(f"[*] SKIPPED: DB {db_path} does not exist.")
        
    # Process WAL and SHM if they exist
    wal_path = db_path + "-wal"
    shm_path = db_path + "-shm"
    for extra_file in [wal_path, shm_path]:
        if os.path.exists(extra_file):
            try:
                os.remove(extra_file)
                print(f"[+] PURGE SUCCESS: Extra DB file {extra_file} wiped.")
            except Exception as e:
                print(f"[-] ERROR purging extra DB file {extra_file}: {e}")
                
    # Process CSV
    if os.path.exists(csv_path):
        csv_backup = os.path.join("logs", f"institutional_journal_backup_{timestamp}.csv")
        try:
            shutil.copy2(csv_path, csv_backup)
            print(f"[+] BACKUP SUCCESS: {csv_backup}")
            os.remove(csv_path)
            print(f"[+] PURGE SUCCESS: {csv_path} has been wiped.")
        except Exception as e:
            print(f"[-] ERROR processing CSV: {e}")
    else:
        print(f"[*] SKIPPED: CSV {csv_path} does not exist.")
        
    print("==========================================================================")
    print("   [ SYSTEM STERILIZED ] : AUREXIS V2 IS READY FOR COLD BOOT IGNITION")
    print("==========================================================================")

if __name__ == '__main__':
    factory_reset()
