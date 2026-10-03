import os
import shutil
import glob
from pathlib import Path

def factory_reset():
    print("==================================================")
    print(">> AUREXIS V2: PREPARING FORWARD TEST ENVIRONMENT")
    print("==================================================")
    
    # 1. Clear SQLite Databases (State, Ledger, Memory)
    dbs = glob.glob("*.db") + glob.glob("data/*.db") + glob.glob("src/data/*.db")
    for db in dbs:
        try:
            os.remove(db)
            print(f"[CLEARED] Database file removed: {db}")
        except Exception as e:
            print(f"[ERROR] Could not remove {db}: {e}")

    # 2. Clear Log Files
    logs = glob.glob("*.log") + glob.glob("logs/*.log") + glob.glob("logs/*.txt")
    for log_file in logs:
        try:
            os.remove(log_file)
            print(f"[CLEARED] Log file removed: {log_file}")
        except Exception as e:
            print(f"[ERROR] Could not remove {log_file}: {e}")
            
    # 3. Clear State/Ghost Targets JSON files
    jsons = glob.glob("*_targets.json") + glob.glob("state*.json")
    for j in jsons:
        try:
            os.remove(j)
            print(f"[CLEARED] State file removed: {j}")
        except Exception as e:
            print(f"[ERROR] Could not remove {j}: {e}")

    # 4. Clear Python Caches
    for p in Path(".").rglob("__pycache__"):
        if p.is_dir():
            try:
                shutil.rmtree(p)
                print(f"[CLEARED] Cache removed: {p}")
            except:
                pass

    print("\n[OK] FACTORY RESET COMPLETE!")
    print("[OK] System is 100% clean and ready for Forward Testing on Monday.")
    print("To start the bot, run: python run_live.py")
    print("==================================================")

if __name__ == "__main__":
    factory_reset()
