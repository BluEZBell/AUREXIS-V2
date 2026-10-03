import os

def patch_harvester_init():
    file_path = 'src/strategy/alpha_harvester.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update __init__
    init_target = '''        # Subscriptions
        self.event_bus.subscribe(CommandEvent, self.process_command)
        self.event_bus.subscribe(TickEvent, self.process_tick)'''
        
    init_replace = '''        self._tactical_halt_active = False
        self._last_tick_day = None
        
        # Subscriptions
        self.event_bus.subscribe(CommandEvent, self.process_command)
        self.event_bus.subscribe(TickEvent, self.process_tick)
        from src.core.event_bus import StrategyStateEvent
        self.event_bus.subscribe(StrategyStateEvent, self._handle_strategy_state)'''

    if init_target in content:
        content = content.replace(init_target, init_replace)
        print("? Added init vars and subscription")
    else:
        print("?? Could not patch __init__")

    # 2. Add _handle_strategy_state
    handler_target = '''    async def check_whipsaw_lock(self, ind: dict) -> bool:'''
    
    handler_code = '''    async def _handle_strategy_state(self, event):
        if getattr(event, "cycle_state", "") == "TACTICAL_HALT":
            if not self._tactical_halt_active:
                logger.critical("System locked down for the day. TACTICAL HALT activated.")
                self._tactical_halt_active = True
                self.auto_sniper = False

    async def check_whipsaw_lock(self, ind: dict) -> bool:'''
    
    if handler_target in content:
        content = content.replace(handler_target, handler_code)
        print("? Added _handle_strategy_state")
    else:
        print("?? Could not patch handler")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    patch_harvester_init()
