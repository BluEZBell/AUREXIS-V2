import re

with open('src/strategy/alpha_harvester.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''                    if latency_s > 0.5:
                        # Log sparsely to avoid spam during latency spikes
                        if latency_s < 60.0:
                            logger.warning(f"LATENCY ARMOR: Stale tick rejected (Latency: {latency_s*1000:.1f}ms > 500ms).")'''

replacement = '''                    # Operation: HFT Aggression - Clock Drift Fix
                    # Increased latency tolerance to 1.5s to prevent OS drift from falsely dropping ticks
                    if latency_s > 1.5:
                        # Log sparsely to avoid spam during latency spikes
                        if latency_s < 60.0:
                            logger.warning(f"LATENCY ARMOR: Stale tick rejected (Latency: {latency_s*1000:.1f}ms > 1500ms).")'''

if target in content:
    content = content.replace(target, replacement)
    with open('src/strategy/alpha_harvester.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched Latency Armor in alpha_harvester.py")
else:
    print("Target not found.")

