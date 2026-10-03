import re

with open('src/execution/risk_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''    async def calculate_lot_size(self, equity: float, atr: float = None, sl_points: float = None, conviction: float = 1.0, oracle_probability: float = None, regime: str = "UNKNOWN", mtf_volume_confirmed: bool = False) -> float:'''

replacement = '''    async def calculate_lot_size(self, equity: float, atr: float = None, sl_points: float = None, conviction: float = 1.0, oracle_probability: float = None, regime: str = "UNKNOWN", mtf_volume_confirmed: bool = False, is_hyper_scale: bool = False) -> float:'''

if target in content:
    content = content.replace(target, replacement)
    with open('src/execution/risk_manager.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched calculate_lot_size signature")
else:
    print("Target not found.")

