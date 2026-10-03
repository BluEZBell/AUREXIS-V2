import os
import sys
import asyncio
import time

# Create mock scripts
mock_preflight = """import sys, time
print("Preflight running...")
time.sleep(1)
if len(sys.argv) > 1 and sys.argv[1] == "fail":
    sys.exit(1)
sys.exit(0)
"""
mock_main = """import sys, time
print("Main engine running...")
time.sleep(2)
print("Main engine crashing...")
sys.exit(1)
"""
mock_eod = """import sys, time
print("EOD tearsheet generating...")
time.sleep(1)
print("Report: /path/to/report.pdf")
"""
mock_alpha = """import sys, time
print("Alpha tuner running...")
time.sleep(1)
print("Parameters: X=1, Y=2")
"""

with open("mock_preflight.py", "w") as f: f.write(mock_preflight)
with open("mock_main.py", "w") as f: f.write(mock_main)
with open("mock_eod.py", "w") as f: f.write(mock_eod)
with open("mock_alpha.py", "w") as f: f.write(mock_alpha)

# Now we will import the supervisor and run it with some patches.
import aurexis_supervisor

aurexis_supervisor.PREFLIGHT_SCRIPT = "mock_preflight.py"
aurexis_supervisor.MAIN_SCRIPT = "mock_main.py"
aurexis_supervisor.EOD_TEARSHEET_SCRIPT = "mock_eod.py"
aurexis_supervisor.ALPHA_TUNER_SCRIPT = "mock_alpha.py"

# We want to patch EOD_TIME so it triggers very soon.
from datetime import datetime, timedelta
target = datetime.now() + timedelta(seconds=15)
aurexis_supervisor.EOD_TIME = target.time()
aurexis_supervisor.RESTART_COOLDOWN = 2.0

supervisor = aurexis_supervisor.Supervisor()
asyncio.run(supervisor.start())
