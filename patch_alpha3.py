import re

with open('src/core/alpha.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_fetch = '''        def _fetch_mtf():
            m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 50)
            h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 50)
            dxy = mt5.symbol_info_tick("DXY")
            us10y = mt5.symbol_info_tick("US10Y")
            vix = mt5.symbol_info_tick("VIX")
            return m15, h1, dxy, us10y, vix

        data = await run_mt5_task(_fetch_mtf)
        if not data:
            return Signal(direction="NONE", conviction_score=0.0, implied_volatility=0.0, initial_invalidation_level=0.0)
            
        m15, h1, dxy, us10y, vix = data'''

new_fetch = '''        def _fetch_mtf():
            m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 50)
            h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 50)
            m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 10)
            dxy = mt5.symbol_info_tick("DXY")
            us10y = mt5.symbol_info_tick("US10Y")
            vix = mt5.symbol_info_tick("VIX")
            return m15, h1, m5, dxy, us10y, vix

        data = await run_mt5_task(_fetch_mtf)
        if not data:
            return Signal(direction="NONE", conviction_score=0.0, implied_volatility=0.0, initial_invalidation_level=0.0)
            
        m15, h1, m5, dxy, us10y, vix = data'''

content = content.replace(old_fetch, new_fetch)

old_logic = '''            bullish_structure = (bid > h1_ema20) and (m15_ema9 > m15_ema21) and (bid > m15_ema9)
            bearish_structure = (ask < h1_ema20) and (m15_ema9 < m15_ema21) and (ask < m15_ema9)
            
            if bullish_structure:
                signal_dir = "BUY"
                conviction = 100.0
            elif bearish_structure:
                signal_dir = "SELL"
                conviction = 100.0
                
            # FAKE-OUT PREVENTION & SAR
            if signal_dir == "BUY":
                if bid >= vah and has_upper_sweep:
                    logger.info("ALPHA TRAP DETECTED: Institutional Sell Wall (Upper Sweep at VAH). Reversing BUY to SAR SELL.")
                    signal_dir = "SELL"
                    conviction = 100.0
                    is_trap = True
            elif signal_dir == "SELL":
                if ask <= val and has_lower_sweep:
                    logger.info("ALPHA TRAP DETECTED: Institutional Buy Wall (Lower Sweep at VAL). Reversing SELL to SAR BUY.")
                    signal_dir = "BUY"
                    conviction = 100.0
                    is_trap = True'''

new_logic = '''            bullish_structure = (bid > h1_ema20) and (m15_ema9 > m15_ema21) and (bid > m15_ema9)
            bearish_structure = (ask < h1_ema20) and (m15_ema9 < m15_ema21) and (ask < m15_ema9)
            
            m15_atr_val = self._calculate_atr(m15_highs, m15_lows, m15_closes, 14)
            ind_dict = {
                'adx_m15': calc_adx(m15_highs, m15_lows, m15_closes, 14)[-1] if len(m15) >= 28 else 20.0,
                'atr_m15': m15_atr_val,
                'm5_range_10': max([x['high'] for x in m5]) - min([x['low'] for x in m5]) if m5 is not None and len(m5) > 0 else 0.0,
                'ema50_h1': self._calculate_ema(h1_closes, 50),
                'curr_price': bid,
                'rsi': calc_rsi(m15_closes, 14)[-1] if len(m15) >= 15 else 50.0
            }
            regime_state = await self.radar.classify_regime(ind_dict) if self.radar else None
            active_regime = regime_state.regime_type.value if regime_state else "UNKNOWN"
            
            if active_regime == "RANGE":
                # Mean-reversion boundary fading
                if bid >= vah:
                    signal_dir = "SELL"
                    conviction = 100.0
                    is_trap = True
                    logger.info("ALPHA RANGE FADE: Mean-reversion SELL at VAH.")
                elif ask <= val:
                    signal_dir = "BUY"
                    conviction = 100.0
                    is_trap = True
                    logger.info("ALPHA RANGE FADE: Mean-reversion BUY at VAL.")
            else:
                if bullish_structure:
                    signal_dir = "BUY"
                    conviction = 100.0
                elif bearish_structure:
                    signal_dir = "SELL"
                    conviction = 100.0
                    
                # FAKE-OUT PREVENTION & SAR
                if signal_dir == "BUY":
                    if bid >= vah and has_upper_sweep:
                        logger.info("ALPHA TRAP DETECTED: Institutional Sell Wall (Upper Sweep at VAH). Reversing BUY to SAR SELL.")
                        signal_dir = "SELL"
                        conviction = 100.0
                        is_trap = True
                elif signal_dir == "SELL":
                    if ask <= val and has_lower_sweep:
                        logger.info("ALPHA TRAP DETECTED: Institutional Buy Wall (Lower Sweep at VAL). Reversing SELL to SAR BUY.")
                        signal_dir = "BUY"
                        conviction = 100.0
                        is_trap = True'''

content = content.replace(old_logic, new_logic)

with open('src/core/alpha.py', 'w', encoding='utf-8') as f:
    f.write(content)
