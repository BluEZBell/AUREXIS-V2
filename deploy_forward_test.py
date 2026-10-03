import os
import shutil
import time
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

def create_archive_dir():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = Path("archive") / f"pre_forward_test_{timestamp}"
    archive_dir.mkdir(parents=True, exist_ok=True)
    return archive_dir

def archive_files(archive_dir: Path):
    print("[*] Task 1: Data Sanitization (Archiving .db and .log files)")
    project_root = Path(".")
    
    db_dir = project_root / "db"
    if db_dir.exists():
        for db_file in db_dir.glob("*.db"):
            dest = archive_dir / db_file.name
            print(f"    Archiving {db_file} -> {dest}")
            shutil.move(str(db_file), str(dest))
            
    # Move log files from root and logs dir
    for log_file in project_root.glob("*.log"):
        dest = archive_dir / log_file.name
        print(f"    Archiving {log_file} -> {dest}")
        shutil.move(str(log_file), str(dest))
        
    logs_dir = project_root / "logs"
    if logs_dir.exists():
        for log_file in logs_dir.glob("*.log"):
            dest = archive_dir / log_file.name
            print(f"    Archiving {log_file} -> {dest}")
            shutil.move(str(log_file), str(dest))

def validate_environment():
    print("[*] Task 2: Environment Validation")
    load_dotenv()
    
    critical_keys = ["MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    missing_keys = []
    
    for key in critical_keys:
        val = os.getenv(key)
        if not val or not str(val).strip():
            missing_keys.append(key)
            
    if missing_keys:
        print("\n[CRITICAL] Aborting deployment! Missing or empty critical environment variables:")
        for key in missing_keys:
            print(f"  - {key}")
        print("\nPlease configure these keys in your .env file before starting Forward Testing.")
        exit(1)
        
    print("    All critical environment variables are verified.")

def check_oracle_model():
    print("[*] Task 3: Model Check")
    model_path = Path("models") / "aurexis_oracle.pkl"
    joblib_path = Path("models") / "aurexis_oracle.joblib"
    
    if not model_path.exists() and not joblib_path.exists():
        print(f"    [WARNING] ML Oracle model not found at {model_path}. Bot will run in PASS_THROUGH mode.")
    else:
        print(f"    ML Oracle model found. Inference is ready.")

def main():
    print("==================================================")
    print("    AUREXIS FORWARD TESTING INITIALIZATION")
    print("==================================================\n")
    
    archive_dir = create_archive_dir()
    
    archive_files(archive_dir)
    print("")
    
    validate_environment()
    print("")
    
    check_oracle_model()
    print("")
    
    print("[*] All systems GO. Workspace is completely sanitized for Out-of-Sample testing.\n")
    print("Launching AUREXIS Watchdog in:")
    for i in range(5, 0, -1):
        print(f" {i}...")
        time.sleep(1)
        
    print("\n>>> HANDOVER TO WATCHDOG <<<")
    try:
        subprocess.run(["python", "aurexis_watchdog.py"])
    except KeyboardInterrupt:
        print("\n[!] Watchdog terminated by user.")

if __name__ == "__main__":
    main()
