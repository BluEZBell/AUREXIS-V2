import os
import re

def patch_mfe():
    file_path = 'src/execution/sentinel.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Add StrategyStateEvent import
    import_target = '''import src.core.config as config'''
    import_replace = '''import src.core.config as config
from src.core.event_bus import StrategyStateEvent'''
    if import_target in content and 'StrategyStateEvent' not in content:
        content = content.replace(import_target, import_replace)
        print("? Added StrategyStateEvent import")

    # 2. Add subscription to __init__
    init_target = '''        self.event_bus.subscribe(StructuralTrendEvent, self._handle_structure)'''
    init_replace = '''        self.event_bus.subscribe(StructuralTrendEvent, self._handle_structure)
        self.event_bus.subscribe(StrategyStateEvent, self._handle_strategy_state)'''
    if init_target in content:
        content = content.replace(init_target, init_replace)
        print("? Added StrategyStateEvent subscription")

    # 3. Add handler
    handler_target = '''    async def _handle_structure(self, event: StructuralTrendEvent):'''
    handler_replace = '''    async def _handle_strategy_state(self, event: StrategyStateEvent):
        self._latest_atr_m15 = getattr(event, "atr_m15", 0.0)

    async def _handle_structure(self, event: StructuralTrendEvent):'''
    if handler_target in content:
        content = content.replace(handler_target, handler_replace)
        print("? Added _handle_strategy_state")

    # 4. Replace profit floor calculation
    # We will replace from loor = None up to logger.info(f"MFE Vault:
    calc_target = '''            floor = None
            activation_tier_2 = spread_cost_usd * 10.0
            activation_tier_1 = spread_cost_usd * 4.0
            activation_tier_0 = spread_cost_usd * 2.0
            
            if new_mfe >= activation_tier_2:
                floor = new_mfe * 0.5  # 50% Trailing Free-Roll
            elif new_mfe >= activation_tier_1:
                floor = spread_cost_usd * 1.5  # Solid Break-Even
            elif new_mfe >= activation_tier_0:
                floor = spread_cost_usd * 0.5  # Micro-Defense (Covers basic friction, guarantees green)
                
            current_floor = self.profit_floors.get(ticket)
            if floor is not None and (current_floor is None or floor > current_floor):
                self.profit_floors[ticket] = floor
                
                last_logged = self._last_logged_floor.get(ticket, -999.0)
                # Require at least 0.10 difference to prevent micro-spread flutter spam
                if floor >= last_logged + 0.10:
                    logger.info(f"MFE Vault: Locking profit floor at  for Ticket {ticket}")
                    self._last_logged_floor[ticket] = floor'''
                    
    calc_replace = '''            atr_m15 = getattr(self, '_latest_atr_m15', 0.0)
            ATR_TRAILING_MULTIPLIER = 2.5
            
            if atr_m15 > 0.0 and sym_info.trade_tick_size > 0:
                atr_allowance_ticks = atr_m15 / sym_info.trade_tick_size
            else:
                atr_allowance_ticks = 200.0  # Fallback to 200.0 points
                
            dynamic_allowance_usd = atr_allowance_ticks * ATR_TRAILING_MULTIPLIER * sym_info.trade_tick_value * pos.volume
            new_dynamic_floor = new_mfe - dynamic_allowance_usd
            
            # Base protection layers (Break-even locks)
            activation_tier_1 = spread_cost_usd * 4.0
            activation_tier_0 = spread_cost_usd * 2.0
            
            proposed_floor = None
            if new_mfe >= activation_tier_1:
                proposed_floor = spread_cost_usd * 1.5
            elif new_mfe >= activation_tier_0:
                proposed_floor = spread_cost_usd * 0.5
                
            # Use the higher of the base break-even or the ATR dynamic floor
            if proposed_floor is not None:
                new_dynamic_floor = max(new_dynamic_floor, proposed_floor)
                
            current_floor = self.profit_floors.get(ticket)
            
            floor = None
            if current_floor is not None:
                floor = max(current_floor, new_dynamic_floor)
            elif new_dynamic_floor > 0:
                floor = new_dynamic_floor
                
            if floor is not None and (current_floor is None or floor > current_floor):
                self.profit_floors[ticket] = floor
                
                last_logged = self._last_logged_floor.get(ticket, -999.0)
                if floor >= last_logged + 0.10:
                    logger.info(f"MFE Vault: Locking profit floor at  for Ticket {ticket}")
                    self._last_logged_floor[ticket] = floor'''

    # We need to make sure the target string exactly matches what is in the file.
    # The file has: logger.info(f"MFE Vault: Locking profit floor at  for Ticket {ticket}")
    # Wait, in Phase 6 I accidentally wrote logger.info(f"MFE Vault: Locking profit floor at  for Ticket {ticket}") ?
    # Let me check what is in the file!
    pass

if __name__ == '__main__':
    patch_mfe()
