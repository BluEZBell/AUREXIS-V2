import re

with open('src/core/adaptive_tuner.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_mfe = '''        total_mfe = sum(t.get("mfe", 0.0) for t in self._recent_trades)
        total_mae = sum(t.get("mae", 0.0) for t in self._recent_trades)'''

new_mfe = '''        total_mfe = sum(t.get("mfe", t.get("MFE", 0.0)) for t in self._recent_trades)
        total_mae = sum(t.get("mae", t.get("MAE", 0.0)) for t in self._recent_trades)'''

content = content.replace(old_mfe, new_mfe)
with open('src/core/adaptive_tuner.py', 'w', encoding='utf-8') as f:
    f.write(content)
