import re

with open('src/strategy/alpha_harvester.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''        self.event_bus.subscribe(CommandEvent, self.process_command)
        self._last_tick_time = 0
        self.data_filter = DataIntegrityFilter()'''

replacement = '''        self.event_bus.subscribe(CommandEvent, self.process_command)
        self._last_tick_time = 0
        self._last_tick_bid = 0.0
        self.data_filter = DataIntegrityFilter()'''

if target in content:
    content = content.replace(target, replacement)
    with open('src/strategy/alpha_harvester.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched initialization in alpha_harvester.py")
else:
    print("Target not found.")

