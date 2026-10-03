import re

with open('run_live.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_oracle = '''        from src.core.alpha import RegimeRadar, MLOracle, AlphaScorer
        radar = RegimeRadar(self.event_bus)
        oracle = MLOracle(self.event_bus)'''

new_oracle = '''        from src.core.alpha import RegimeRadar, MLOracle, AlphaScorer
        radar = RegimeRadar(self.event_bus)
        oracle = MLOracle(self.event_bus)
        await oracle.load_model()'''

content = content.replace(old_oracle, new_oracle)

with open('run_live.py', 'w', encoding='utf-8') as f:
    f.write(content)
