import re

with open('src/strategy/alpha_harvester.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update __init__ to add self.auto_sniper = True and subscribe to CommandEvent
init_target = '''        self.strategy_id = "CENTRAL_ORCHESTRATOR"
        self._running = False'''

init_replace = '''        self.strategy_id = "CENTRAL_ORCHESTRATOR"
        self._running = False
        self.auto_sniper = True  # DEFAULT ARMED STATE
        
        from src.core.event_bus import CommandEvent
        self.event_bus.subscribe(CommandEvent, self.process_command)'''

content = content.replace(init_target, init_replace)

# 2. Add process_command method
method_target = '''    async def _handle_signal_execution(self, symbol: str, bid: float, ask: float, tick_ingest_time: float = 0.0):'''

method_replace = '''    async def process_command(self, event) -> None:
        if getattr(event, 'action', '') == "TOGGLE_AUTO_SNIPER":
            self.auto_sniper = not self.auto_sniper
            logger.info(f"Auto-Sniper {'ENGAGED' if self.auto_sniper else 'DISENGAGED'}")

    async def _handle_signal_execution(self, symbol: str, bid: float, ask: float, tick_ingest_time: float = 0.0):'''

content = content.replace(method_target, method_replace)

# 3. Guard the signal execution in start() with self.auto_sniper
start_target = '''                    if not spread_blackout and not news_blackout:
                        asyncio.create_task(self._handle_signal_execution(config.TRADING_SYMBOL, tick.bid, tick.ask, tick_ingest_start))'''

start_replace = '''                    if not spread_blackout and not news_blackout:
                        if self.auto_sniper:
                            asyncio.create_task(self._handle_signal_execution(config.TRADING_SYMBOL, tick.bid, tick.ask, tick_ingest_start))'''

content = content.replace(start_target, start_replace)

with open('src/strategy/alpha_harvester.py', 'w', encoding='utf-8') as f:
    f.write(content)
