import re

with open('src/core/event_bus.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''    order_type: str = "PROBE" # "PROBE" or "SET"
    regime: str = "UNKNOWN"
    mtf_volume_confirmed: bool = False'''

replacement = '''    order_type: str = "PROBE" # "PROBE" or "SET"
    regime: str = "UNKNOWN"
    mtf_volume_confirmed: bool = False
    is_hyper_scale: bool = False'''

if target in content:
    content = content.replace(target, replacement)
    with open('src/core/event_bus.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched SignalEvent in event_bus.py")
else:
    print("Target not found. Try again.")

