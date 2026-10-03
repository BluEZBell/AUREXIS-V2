import re

with open('src/core/alpha.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_macro = '''        if macro_valid:
            macro_val = self.latest_macro.dxy + (self.latest_macro.us10y * 10.0) - (self.latest_macro.vix * 2.0)
            self.macro_tick_history.append(macro_val)
            if len(self.macro_tick_history) > 10:'''

new_macro = '''        if macro_valid:
            macro_val = self.latest_macro.dxy + (self.latest_macro.us10y * 10.0) - (self.latest_macro.vix * 2.0)
            if not self.macro_tick_history or abs(self.macro_tick_history[-1] - macro_val) > 0.00001:
                self.macro_tick_history.append(macro_val)
            if len(self.macro_tick_history) > 10:'''

content = content.replace(old_macro, new_macro)
with open('src/core/alpha.py', 'w', encoding='utf-8') as f:
    f.write(content)
