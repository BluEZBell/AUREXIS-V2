import re

with open('src/core/alpha.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''        action = "SAR" if is_trap else "CORE"
        if not is_trap and signal_dir != "NONE" and self._positions:
            has_opposite = False
            for ticket, p in self._positions.items():
                pos_is_buy = (p['type'] == 'BUY')
                if pos_is_buy and signal_dir == "SELL":
                    has_opposite = True
                elif not pos_is_buy and signal_dir == "BUY":
                    has_opposite = True
            
            if has_opposite:
                action = "SAR"
                logger.info(f"ALPHA TRIGGER SAR: Structural trend inverted. Dispatching SAR to {signal_dir}")
                
        if signal_dir != "NONE":'''

replacement = '''        is_hyper_scale = False
        if of_state and signal_dir != "NONE":
            # Operation: Convex Risk Allocation & Hyper-Scaling
            # Check if ML Conviction > 85.0 and Extreme Order Flow
            if conviction > 85.0:
                if (signal_dir == "BUY" and of_state.delta_momentum > 10.0) or (signal_dir == "SELL" and of_state.delta_momentum < -10.0):
                    is_hyper_scale = True
                    logger.info(f"HYPER-SCALE TRIGGERED: Conviction={conviction:.1f}, Delta Momentum={of_state.delta_momentum:.2f}")

        action = "SAR" if is_trap else "CORE"
        if not is_trap and signal_dir != "NONE" and self._positions:
            has_opposite = False
            same_dir_prices = []
            for ticket, p in self._positions.items():
                pos_is_buy = (p['type'] == 'BUY')
                if pos_is_buy and signal_dir == "SELL":
                    has_opposite = True
                elif not pos_is_buy and signal_dir == "BUY":
                    has_opposite = True
                elif pos_is_buy and signal_dir == "BUY":
                    same_dir_prices.append(p.get('price_open', p.get('price', 0.0)))
                elif not pos_is_buy and signal_dir == "SELL":
                    same_dir_prices.append(p.get('price_open', p.get('price', 0.0)))
            
            if has_opposite:
                action = "SAR"
                logger.info(f"ALPHA TRIGGER SAR: Structural trend inverted. Dispatching SAR to {signal_dir}")
            else:
                # Same direction Pyramiding Distance Check
                if len(same_dir_prices) > 0 and (ask > 0 and bid > 0):
                    point_val = mt5.symbol_info(symbol).point
                    if point_val > 0:
                        if signal_dir == "BUY":
                            closest_price = max(same_dir_prices)
                            distance_pts = (ask - closest_price) / point_val
                        else:
                            closest_price = min(same_dir_prices)
                            distance_pts = (closest_price - bid) / point_val
                        
                        atr_pts = (m15_atr_val / 1e-5) if m15_atr_val else 20.0
                        required_distance_pts = atr_pts * (0.5 if is_hyper_scale else 1.0)
                        
                        if distance_pts < required_distance_pts:
                            logger.info(f"ALPHA REJECT {signal_dir}: Pyramiding distance {distance_pts:.1f} pts < required {required_distance_pts:.1f} pts (is_hyper_scale={is_hyper_scale}).")
                            return Signal(direction="NONE", conviction_score=0.0, implied_volatility=0.0, initial_invalidation_level=0.0)
                
        if signal_dir != "NONE":'''

if target in content:
    content = content.replace(target, replacement)
    with open('src/core/alpha.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched logic in alpha.py")
else:
    print("Target not found.")

