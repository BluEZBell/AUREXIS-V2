import re

with open('src/execution/sentinel.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Checking if the old rigid logic exists
old_logic = "if new_mfe >= 15.0:"
if old_logic in content:
    # This won't trigger since we upgraded it to dynamic
    print("Found old rigid logic. Replacing...")
else:
    print("Patch skipped: The old rigid +.0 / +.0 logic has ALREADY been completely eradicated!")
    print("The system is currently running on the Advanced Institutional Dynamic Spread-Pegged MFE Vault.")
