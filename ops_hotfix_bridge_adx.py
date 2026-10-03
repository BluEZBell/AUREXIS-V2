import os

def hotfix_bridge_adx():
    file_path = 'src/execution/bridge.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''                    if live_price_above_m15_ema20 and (ema20_sloping_up or m5_strong_bull or bullish_structure_reversal):
                        m15_trend = "BULLISH"
                    elif live_price_below_m15_ema20 and (ema20_sloping_down or m5_strong_bear or bearish_structure_reversal):
                        m15_trend = "BEARISH"
                    else:
                        m15_trend = "NEUTRAL"'''
    
    replace = '''                    # Calculate ADX early for Regime Filter
                    m15_highs_for_adx = np.array([x['high'] for x in m15_rates_closed])
                    m15_lows_for_adx = np.array([x['low'] for x in m15_rates_closed])
                    m15_adx_temp = calc_adx(m15_highs_for_adx, m15_lows_for_adx, m15_closes_closed, 14)[-1]

                    buffer = atr * 0.15
                    if m15_adx_temp < 22.0:
                        m15_trend = "NEUTRAL"
                    else:
                        if m15_ema20 > m15_ema50 + buffer:
                            m15_trend = "BULLISH"
                        elif m15_ema50 > m15_ema20 + buffer:
                            m15_trend = "BEARISH"
                        else:
                            m15_trend = "NEUTRAL"'''

    if target in content:
        content = content.replace(target, replace)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? Patch applied successfully: Applied ADX filter to M15 structural trend.")
    else:
        print("?? Patch skipped: Target string not found.")

if __name__ == '__main__':
    hotfix_bridge_adx()
