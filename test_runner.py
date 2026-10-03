import subprocess
import sys

def test_run():
    print("Running python logic...")
    result = subprocess.run([sys.executable, "test_logic.py"], capture_output=True, text=True)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    assert result.returncode == 0
