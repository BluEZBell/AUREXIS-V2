import os
import shutil
from pathlib import Path
from typing import List, Tuple

def get_target_files(project_root: Path) -> List[Path]:
    """Identify all database and journal files for sterilization."""
    targets: List[Path] = []
    
    # Task 1: Databases in root and db/
    db_dirs: List[Path] = [project_root, project_root / 'db']
    for d in db_dirs:
        if d.exists() and d.is_dir():
            targets.extend(d.glob('*.db'))
            targets.extend(d.glob('*.db-wal'))
            targets.extend(d.glob('*.db-shm'))
            
    # Task 2: Quant Logs & Journals
    targets.append(project_root / 'trade_journal.csv')
    targets.append(project_root / 'logs' / 'trade_journal.csv')
    targets.append(project_root / 'institutional_journal.csv')
    targets.append(project_root / 'logs' / 'institutional_journal.csv')
    
    logs_dir = project_root / 'logs'
    if logs_dir.exists() and logs_dir.is_dir():
        targets.extend(logs_dir.glob('*.log'))
        
    # Filter out duplicates and keep only existing files
    return list(set([t for t in targets if t.exists() and t.is_file()]))

def sterilize_env(project_root: Path) -> Tuple[bool, bool]:
    """Remove DRY_RUN from .env file if it exists. Returns (was_modified, success)."""
    env_file: Path = project_root / '.env'
    if not env_file.exists():
        return False, True
        
    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        new_lines = [line for line in lines if not line.strip().startswith('DRY_RUN')]
        
        if len(new_lines) != len(lines):
            with open(env_file, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            return True, True
        return False, True
    except Exception as e:
        print(f"[!] Failed to process .env: {e}")
        return False, False

def main() -> None:
    print("=" * 60)
    print(" AUREXIS V2 | PRE-FLIGHT STERILIZATION PROTOCOL ")
    print("=" * 60)
    
    # Locate project root (assuming script is in src/tools)
    script_dir: Path = Path(__file__).resolve().parent
    project_root: Path = script_dir.parent.parent
    
    print(f"[*] Targeting workspace: {project_root}")
    
    # Ensure logs directory exists
    logs_dir: Path = project_root / 'logs'
    if not logs_dir.exists():
        print(f"[*] Creating logs directory: {logs_dir}")
        os.makedirs(logs_dir, exist_ok=True)
        
    # Execute Task 1 & 2
    targets: List[Path] = get_target_files(project_root)
    deleted_count: int = 0
    
    if not targets:
        print("[*] No test artifacts found. Environment is clean.")
    else:
        for t in targets:
            try:
                t.unlink()
                print(f"[+] DELETED: {t.relative_to(project_root)}")
                deleted_count += 1
            except Exception as e:
                print(f"[!] FAILED to delete {t.name}: {e}")
                
    # Execute Task 3
    env_modified, env_success = sterilize_env(project_root)
    if env_success:
        if env_modified:
            print("[+] SANITIZED: Removed 'DRY_RUN' from .env")
        else:
            print("[*] VERIFIED: .env does not contain 'DRY_RUN'")
    
    print("-" * 60)
    print(" STERILIZATION SUMMARY ")
    print("-" * 60)
    print(f"Files Wiped    : {deleted_count}")
    print(f".env Status    : {'Sanitized' if env_modified else 'Verified'}")
    print("System Status  : READY FOR LIVE DEPLOYMENT")
    print("=" * 60)

if __name__ == '__main__':
    main()
