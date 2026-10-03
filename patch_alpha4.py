import re

with open('src/core/alpha.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_return = '''                atr=20.0,
                dynamic_target=poc'''

new_return = '''                atr=m15_atr_val / 1e-5 if m15_atr_val else 20.0,
                dynamic_target=poc'''

content = content.replace(old_return, new_return)

with open('src/core/alpha.py', 'w', encoding='utf-8') as f:
    f.write(content)
