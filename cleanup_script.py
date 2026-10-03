import os
import shutil
from pathlib import Path

def cleanup():
    # Task 1
    for f in ["ledger_8000.db", "scratch_report.log"]:
        if os.path.exists(f):
            os.remove(f)
            
    if os.path.exists("logs"):
        for p in Path("logs").glob("*.log*"):
            p.unlink()
            
    # Task 2
    for p in Path("src/core/__pycache__").glob("*.nbc"):
        p.unlink()
    for p in Path("src/core/__pycache__").glob("*.nbi"):
        p.unlink()
        
    for p in Path(".").rglob("__pycache__"):
        if p.is_dir():
            shutil.rmtree(p)
            
    for p in Path(".").rglob(".pytest_cache"):
        if p.is_dir():
            shutil.rmtree(p)

if __name__ == "__main__":
    cleanup()
