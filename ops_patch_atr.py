import os
import re

def patch_sentinel():
    file_path = 'src/execution/sentinel.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace the old tier logic with the dynamic ATR logic
    target_pattern = r'            floor = None\s+activation_tier_2 = spread_cost_usd \* 10\.0.*?self\._last_logged_floor\[ticket\] = floor'
    
    replace_str = '''            atr_m15 = getattr(self, '_latest_atr_m15', 0.0)
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
                    logger.info(f"MFE Vault: Locking profit floor at ${floor:.2f} for Ticket {ticket}")
                    self._last_logged_floor[ticket] = floor'''
    
    content = re.sub(target_pattern, replace_str, content, flags=re.DOTALL)
    
    # Fix the missing Profit variable
    content = re.sub(r'logger\.warning\(f"Tick Sentinel: Executing CLOSE for Ticket \{ticket\}\. Reason: \{close_reason\}\. Profit: "\)', r'logger.warning(f"Tick Sentinel: Executing CLOSE for Ticket {ticket}. Reason: {close_reason}. Profit: ${current_profit:.2f}")', content)

    # 1. Add StrategyStateEvent import
    import_target = 'import src.core.config as config'
    import_replace = '''import src.core.config as config
from src.core.event_bus import StrategyStateEvent'''
    if import_target in content and 'StrategyStateEvent' not in content:
        content = content.replace(import_target, import_replace)

    # 2. Add subscription to __init__
    init_target = '        self.event_bus.subscribe(StructuralTrendEvent, self._handle_structure)'
    init_replace = '''        self.event_bus.subscribe(StructuralTrendEvent, self._handle_structure)
        self.event_bus.subscribe(StrategyStateEvent, self._handle_strategy_state)'''
    if init_target in content and '_handle_strategy_state' not in content:
        content = content.replace(init_target, init_replace)

    # 3. Add handler
    handler_target = '    async def _handle_structure(self, event: StructuralTrendEvent):'
    handler_replace = '''    async def _handle_strategy_state(self, event: StrategyStateEvent):
        self._latest_atr_m15 = getattr(event, "atr_m15", 0.0)

    async def _handle_structure(self, event: StructuralTrendEvent):'''
    if handler_target in content and 'def _handle_strategy_state' not in content:
        content = content.replace(handler_target, handler_replace)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("? sentinel.py patched for Phase 8.5")

if __name__ == '__main__':
    patch_sentinel()
