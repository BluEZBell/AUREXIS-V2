import re

with open('src/core/alpha.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''    target_price: float = 0.0
    dynamic_target: float = 0.0
    atr: float = 0.0'''

replacement = '''    target_price: float = 0.0
    dynamic_target: float = 0.0
    atr: float = 0.0
    is_hyper_scale: bool = False'''

if target in content:
    content = content.replace(target, replacement)
    with open('src/core/alpha.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched Signal in alpha.py")
else:
    print("Target not found.")

