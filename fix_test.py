import re

with open('tests/test_alpha_harvester.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_ind = r'''        harvester._latest_indicators = {
            config.TRADING_SYMBOL: {
                'ema20_m15': 1910, 'ema50_m15': 1900, 'rsi': 50, 'bull_break': False, 'bear_break': False, 'adx': 15
            }
        }'''

new_ind = r'''        harvester._latest_indicators = {
            config.TRADING_SYMBOL: {
                'ema20_m15': 1910, 'ema50_m15': 1900, 'rsi': 50, 'bull_break': False, 'bear_break': False, 'adx': 15,
                'adx_m15': 15.0, 'atr_m15': 10.0, 'm5_range_10': 5.0
            }
        }'''

content = content.replace(old_ind, new_ind)

with open('tests/test_alpha_harvester.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed test_conviction_gate indicators.")
