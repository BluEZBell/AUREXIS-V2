import re

with open('src/core/alpha.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''                atr=m15_atr_val / 1e-5 if m15_atr_val else 20.0,
                dynamic_target=poc,
                is_hyper_scale=is_hyper_scale'''

replacement = '''                atr=m15_atr_val if m15_atr_val else 20.0,
                dynamic_target=poc,
                is_hyper_scale=is_hyper_scale'''

if target in content:
    content = content.replace(target, replacement)
    with open('src/core/alpha.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched atr assignment in alpha.py")
else:
    print("Target not found.")

