import os

def patch_handler():
    file_path = 'src/strategy/alpha_harvester.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    handler_target = '''    async def check_whipsaw_lock(self, ind):'''
    
    handler_code = '''    async def _handle_strategy_state(self, event):
        if getattr(event, "cycle_state", "") == "TACTICAL_HALT":
            if not self._tactical_halt_active:
                logger.critical("System locked down for the day. TACTICAL HALT activated.")
                self._tactical_halt_active = True
                self.auto_sniper = False

    async def check_whipsaw_lock(self, ind):'''
    
    if handler_target in content:
        content = content.replace(handler_target, handler_code)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? Added _handle_strategy_state")
    else:
        print("?? Could not patch handler")

if __name__ == '__main__':
    patch_handler()
