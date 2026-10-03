import re

with open('tests/test_alpha_harvester.py', 'r', encoding='utf-8') as f:
    content = f.read()

pattern = re.compile(r"    ind_data = \{\n        'ema20_m15': 1890, 'ema50_m15': 1900, 'rsi': 40, 'bull_break': False, 'bear_break': True, \n        'adx': 25, 'adx_m15': 30.0, 'macd_hist': -1, 'macd_line': -2, 'macd_signal': -1,\n        'atr_m15': 10.0, 'm5_range_10': 5.0, 'adx_m15_rising': True, 'ema_expansion': True\n    \}")

new_logic = '''    ind_data = {
        'curr_price': 1895.0,
        'bb_lower': 1880.0,
        'bb_upper': 1910.0,
        'ema_20': 1895.0,
        'ema20_m15': 1890, 'ema50_m15': 1900, 'rsi': 50, 'bull_break': False, 'bear_break': True, 
        'adx': 25, 'adx_m15': 30.0, 'macd_hist': -1, 'macd_line': -2, 'macd_signal': -1,
        'atr_m15': 10.0, 'm5_range_10': 5.0, 'adx_m15_rising': True, 'ema_expansion': True
    }'''

new_content = pattern.sub(new_logic, content)

with open('tests/test_alpha_harvester.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Replaced ind_data in tests.")
