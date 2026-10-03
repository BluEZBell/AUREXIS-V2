import re

with open('src/execution/sentinel.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'\s*emergency_sl\s*=\s*equity\s*\*\s*-0\.15', '', content)

old_block = '''            if not close_reason and current_profit <= emergency_sl:
                close_reason = "VIRTUAL_SL"
                logger.critical(f"SENTINEL: EMERGENCY VIRTUAL SL BREACH on Ticket {ticket} at {current_profit:.2f}. Forcing liquidation.")
            elif floor is not None and current_profit <= floor:'''

new_block = '''            if floor is not None and current_profit <= floor:'''

content = content.replace(old_block, new_block)

with open('src/execution/sentinel.py', 'w', encoding='utf-8') as f:
    f.write(content)
