import re

with open('src/strategy/alpha_harvester.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('breakout_score = await self.calculate_breakout_score(ind)', '')

flip_code = '''
    async def log_direction_flip(self):
        if not hasattr(self, 'dir_changes'):
            self.dir_changes = []
        self.dir_changes.append(time.time())
        if len(self.dir_changes) >= 3:
            time_diff = self.dir_changes[-1] - self.dir_changes[-3]
            if time_diff < 3600:
                atr_m15 = self._latest_indicators.get(config.TRADING_SYMBOL, {}).get('atr_m15', 250.0)
                self.whipsaw_locked_until = time.time() + self.param_store.get_whipsaw_lock_time(atr_m15)
                logger.warning("Harvester: Whipsaw mode detected. Halting SET escalation.")
            self.dir_changes = self.dir_changes[-3:]

    async def get_indicators'''

text = text.replace('    async def get_indicators', flip_code)

with open('src/strategy/alpha_harvester.py', 'w', encoding='utf-8') as f:
    f.write(text)
