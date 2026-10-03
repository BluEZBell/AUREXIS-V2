import sys
import os

if __name__ == "__main__":
    print("WARNING: main.py is deprecated and has been forcefully redirected to run_live.py.")
    print("If you are seeing this, please delete your old shortcut and use start_aurexis.bat instead.")
    
    # Force redirect to run_live.py
    import run_live
    run_live.main()
