import sys, time
print("Preflight running...")
time.sleep(1)
if len(sys.argv) > 1 and sys.argv[1] == "fail":
    sys.exit(1)
sys.exit(0)
