import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"c:\Users\bluzp\AUREXISV2\src"
filepath = os.path.join(base_dir, 'execution/bridge.py')

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

bad_str = '''                volume = rm.calculate_lot_size(exec_equity, sl_points)'''

good_str = '''                if getattr(signal, "volume", 0.0) > 0.0:
                    volume = signal.volume
                else:
                    volume = rm.calculate_lot_size(exec_equity, sl_points)'''

if bad_str in content:
    content = content.replace(bad_str, good_str)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ BRIDGE VOLUME CALCULATION RESPECTS SIGNAL VOLUME")
else:
    print("❌ PATTERN NOT FOUND IN BRIDGE")
