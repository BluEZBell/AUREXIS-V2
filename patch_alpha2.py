import re

with open('src/alpha/alpha_scorer.py', 'r', encoding='utf-8') as f:
    content = f.read()

eval_logic = """
            # Phase 23: Multi-Timeframe Precision Alpha Check & Adaptive Regime Correction
            ema50_h1 = float(ind.get('ema50_h1', 0.0))
            macd_hist = float(ind.get('macd_hist', 0.0))
            tick_vol_curr = float(ind.get('tick_vol_curr', 0.0))
            tick_vol_sma = float(ind.get('tick_vol_sma', 1.0))
            curr_price = float(ind.get('curr_price', 0.0))
            atr = float(ind.get('atr_m15', 1e-5))

            vol_velocity = tick_vol_curr / tick_vol_sma if tick_vol_sma > 0 else 1.0
            has_volume_surge = vol_velocity > 1.1

            buy_conviction = 0.0
            sell_conviction = 0.0

            if regime_state.regime_type == "TREND":
                # 1. Macro (H1 Trend)
                macro_trend = "NONE"
                if ema50_h1 > 0:
                    if curr_price > ema50_h1 + (atr * 0.2):
                        macro_trend = "BULLISH"
                    elif curr_price < ema50_h1 - (atr * 0.2):
                        macro_trend = "BEARISH"

                # 2. Micro (M15 Momentum/MACD)
                micro_momentum = "NONE"
                if macd_hist > 0:
                    micro_momentum = "BULLISH"
                elif macd_hist < 0:
                    micro_momentum = "BEARISH"

                if macro_trend == "NONE" or macro_trend != micro_momentum or not has_volume_surge:
                    # MTF Confluence failed. Veto all signals.
                    return AlphaSignal(direction="NONE", score=0.0, regime=regime_state.regime_type, action="NOISE")
                
                # If MTF Confluence passes
                if macro_trend == "BULLISH":
                    buy_conviction = 60.0 + min(30.0, (vol_velocity - 1.0) * 50.0)
                elif macro_trend == "BEARISH":
                    sell_conviction = 60.0 + min(30.0, (vol_velocity - 1.0) * 50.0)

            elif regime_state.regime_type == "RANGE":
                # Alter strategy to Mean-Reversion at extremes instead of trend following
                ema20 = float(ind.get('ema20_m15', 0.0))
                bb_upper = float(ind.get('bb_upper', 0.0))
                std_dev = (bb_upper - ema20) / 2.0 if bb_upper > ema20 else atr
                z_score = (curr_price - ema20) / std_dev if std_dev > 0 else 0.0

                if z_score < -1.5 and has_volume_surge: # Oversold and absorbing
                    buy_conviction = 50.0 + (abs(z_score) * 20.0)
                elif z_score > 1.5 and has_volume_surge: # Overbought and absorbing
                    sell_conviction = 50.0 + (z_score * 20.0)
                else:
                    return AlphaSignal(direction="NONE", score=0.0, regime=regime_state.regime_type, action="NOISE")
"""

pattern = r'            # Phase 23: Multi-Timeframe Precision Alpha Check.*?elif macro_trend == "BEARISH":\n                  sell_conviction = 60\.0 \+ min\(30\.0, \(vol_velocity - 1\.0\) \* 50\.0\)'

content = re.sub(pattern, eval_logic.strip(), content, flags=re.DOTALL)

with open('src/alpha/alpha_scorer.py', 'w', encoding='utf-8') as f:
    f.write(content)
