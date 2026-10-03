import re

with open('src/strategy/alpha_harvester.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''                        soft_tp=signal.dynamic_target,
                        atr=signal.atr
                    )'''

replacement = '''                        soft_tp=signal.dynamic_target,
                        atr=signal.atr,
                        is_hyper_scale=getattr(signal, 'is_hyper_scale', False)
                    )'''

if target in content:
    content = content.replace(target, replacement)
    with open('src/strategy/alpha_harvester.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched SignalEvent in alpha_harvester.py")
else:
    print("Target not found.")

