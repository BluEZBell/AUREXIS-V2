import re

with open('src/execution/tick_sentinel.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''        # Momentum Stall
        if len(self._pos_tick_vols[ticket]) == 20:'''

new_block = '''        # Magnetic Targeting (POC Liquidity Pool)
        soft_tp = self._soft_targets.get(ticket, {}).get('soft_tp', 0.0)
        if soft_tp > 0 and profit_points > (fast_atr * 0.5):
            distance_to_poc = abs(price_current - soft_tp) / point
            if distance_to_poc < (fast_atr * 1.0):
                # We are at or near the POC, aggressively lock profit with tight SL
                trail_sl = price_current - (fast_atr * 0.25 * point) if is_buy else price_current + (fast_atr * 0.25 * point)
                current_sl = self._soft_targets.get(ticket, {}).get('soft_sl', 0.0)
                
                needs_update = False
                if is_buy and (current_sl == 0.0 or trail_sl > current_sl):
                    needs_update = True
                elif not is_buy and (current_sl == 0.0 or trail_sl < current_sl):
                    needs_update = True
                    
                if needs_update:
                    if ticket not in self._soft_targets:
                        self._soft_targets[ticket] = {}
                    self._soft_targets[ticket]['soft_sl'] = trail_sl
                    self._save_ghost_targets()
                    logger.info(f"Magnetic Targeting: Ticket {ticket} near POC ({soft_tp}), trailing SL tightly.")
                    if self.telemetry_logger:
                        self.telemetry_logger.record_sentinel_event(
                            event_name="SL_TRAIL: Magnetic POC",
                            ticket=ticket,
                            reason="Securing profit as price hits institutional liquidity pool (POC)."
                        )

        # Momentum Stall
        if len(self._pos_tick_vols[ticket]) == 20:'''

content = content.replace(old_block, new_block)

with open('src/execution/tick_sentinel.py', 'w', encoding='utf-8') as f:
    f.write(content)
