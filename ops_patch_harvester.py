import os
import re

def patch_harvester():
    file_path = 'src/strategy/alpha_harvester.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update __init__
    init_target = '''        self.current_score = 0.0
        self.whipsaw_locked_until = 0.0
        self.event_bus.subscribe(TickEvent, self.process_tick)'''
        
    init_replace = '''        self.current_score = 0.0
        self.whipsaw_locked_until = 0.0
        self._tactical_halt_active = False
        self._last_tick_day = None
        self.event_bus.subscribe(TickEvent, self.process_tick)
        from src.core.event_bus import StrategyStateEvent
        self.event_bus.subscribe(StrategyStateEvent, self._handle_strategy_state)'''
        
    if init_target in content:
        content = content.replace(init_target, init_replace)
        print("? Added init vars and subscription")
    else:
        print("?? Could not patch __init__")

    # 2. Add _handle_strategy_state
    handler_code = '''
    async def _handle_strategy_state(self, event):
        if getattr(event, "cycle_state", "") == "TACTICAL_HALT":
            if not self._tactical_halt_active:
                logger.critical("System locked down for the day. TACTICAL HALT activated.")
                self._tactical_halt_active = True
                self.auto_sniper = False
'''
    # We can inject this right after check_whipsaw_lock
    lock_target = '''    async def check_whipsaw_lock(self, ind: dict) -> bool:'''
    if lock_target in content:
        content = content.replace(lock_target, handler_code + '\n' + lock_target)
        print("? Added _handle_strategy_state")
    else:
        print("?? Could not patch check_whipsaw_lock")

    # 3. Process tick halt check and day reset
    tick_target = '''    async def process_tick(self, event: TickEvent):
        current_time = time.time()
        if current_time < self._cooldown_until or current_time - self._last_tick_eval < 5.0:
            return
        self._last_tick_eval = current_time'''
        
    tick_replace = '''    async def process_tick(self, event: TickEvent):
        current_time = time.time()
        if current_time < self._cooldown_until or current_time - self._last_tick_eval < 5.0:
            return
        self._last_tick_eval = current_time
        
        import datetime
        server_time = datetime.datetime.fromtimestamp(event.time, datetime.timezone.utc)
        if self._last_tick_day is not None and server_time.day != self._last_tick_day:
            if self._tactical_halt_active:
                logger.info("New trading day detected (00:00). Lifting Tactical Halt.")
                self._tactical_halt_active = False
                self.risk_manager.halted = False
        self._last_tick_day = server_time.day'''
        
    if tick_target in content:
        content = content.replace(tick_target, tick_replace)
        print("? Added tick processor halt check and day reset")
    else:
        print("?? Could not patch process_tick top")

    # 4. Insert Tactical Halt blocker before the Execution Gateway
    gateway_target = '''            # 2. PHASE 3.5: Execution Gateway
            if self.auto_sniper:
                signal = await self.scorer.evaluate(ind)'''
                
    gateway_replace = '''            # 2. PHASE 3.5: Execution Gateway
            if self._tactical_halt_active:
                # Do not execute Alpha Scorer or open new cycles
                pass
            elif self.auto_sniper:
                signal = await self.scorer.evaluate(ind)'''
                
    if gateway_target in content:
        content = content.replace(gateway_target, gateway_replace)
        print("? Patched Gateway Execution to block on Tactical Halt")
    else:
        print("?? Could not patch Gateway Execution")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    patch_harvester()
