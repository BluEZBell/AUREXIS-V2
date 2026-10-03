import re

with open('src/core/config.py', 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('DRY_RUN = os.getenv("DRY_RUN", "True")', 'DRY_RUN = os.getenv("DRY_RUN", "False")')
with open('src/core/config.py', 'w', encoding='utf-8') as f:
    f.write(content)
