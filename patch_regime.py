import re

with open('src/alpha/alpha_scorer.py', 'r', encoding='utf-8') as f:
    content = f.read()

regime_init = '''class RegimeRadar:
    def __init__(self, event_bus):
        self._last_regime = "UNKNOWN"
        self.consecutive_probe_fails = 0
        self.event_bus = event_bus
        
        from src.core.event_bus import ScoutFailEvent, ScoutSuccessEvent
        self.event_bus.subscribe(ScoutFailEvent, self._handle_scout_fail)
        self.event_bus.subscribe(ScoutSuccessEvent, self._handle_scout_success)
        
    async def _handle_scout_fail(self, event):
        self.consecutive_probe_fails += 1
        
    async def _handle_scout_success(self, event):
        self.consecutive_probe_fails = 0

    async def classify_regime(self, ind: Dict[str, Any]) -> Optional[RegimeState]:'''

content = content.replace('class RegimeRadar:\n    def __init__(self):\n        self._last_regime = "UNKNOWN"\n\n    async def classify_regime(self, ind: Dict[str, Any]) -> Optional[RegimeState]:', regime_init)

regime_logic = '''            # Phase 23: Adaptive Regime Correction
            if self.consecutive_probe_fails >= 2:
                regime_type = "RANGE"
                # Override internal metrics to reflect range constraint
                directional_strength = 0.0
                volatility_index = 1.0
            else:
                if directional_strength > 0.6 and volatility_index > 0.4:
                    regime_type = "TREND"
                elif directional_strength < 0.4 and volatility_index > 0.6:
                    regime_type = "RANGE"
                else:
                    regime_type = "CHOP"'''

content = re.sub(r'            if directional_strength > 0\.6 and volatility_index > 0\.4:\n                regime_type = "TREND"\n            elif directional_strength < 0\.4 and volatility_index > 0\.6:\n                regime_type = "RANGE"\n            else:\n                regime_type = "CHOP"', regime_logic, content)

with open('src/alpha/alpha_scorer.py', 'w', encoding='utf-8') as f:
    f.write(content)
