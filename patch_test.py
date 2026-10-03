import re

with open('tests/test_alpha_harvester.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r"'curr_price': 1895\.0,", "'curr_price': 1870.0,", text)
text = re.sub(r"'macd_hist': -1,", "'macd_hist': -10, 'macd_hist_slope': -2,", text)

with open('tests/test_alpha_harvester.py', 'w', encoding='utf-8') as f:
    f.write(text)
