import asyncio
from src.core.adaptive_tuner import AdaptiveTuner
from src.core.telemetry import TelemetryLogger
from src.core.alpha import AlphaScorer
from src.core.hud import TelemetryState

import pytest

@pytest.mark.asyncio
async def test():
    state = TelemetryState()
    
    class DummyAlphaScorer:
        def __init__(self):
            self.dynamic_core_min = 85.0
            self.macro_weight = 45.0
            self.micro_weight = 30.0
            self.vol_weight = 25.0
        def tune_weights(self, core_min, macro_w, micro_w, vol_w):
            self.dynamic_core_min = core_min
            self.macro_weight = macro_w
            self.micro_weight = micro_w
            self.vol_weight = vol_w

    scorer = DummyAlphaScorer()
    tuner = AdaptiveTuner(scorer, state, window_size=2)
    
    tuner.start()
    
    tuner.on_trade_closed({"MFE": "10.0", "MAE": "-10.0"})
    tuner.on_trade_closed({"MFE": "5.0", "MAE": "-20.0"}) # Ratio = 15 / 30 = 0.5 (<1.5)
    
    await asyncio.sleep(0.1)
    
    print(f"Scorer weights after decay: {scorer.dynamic_core_min}, {scorer.macro_weight}, {scorer.micro_weight}, {scorer.vol_weight}")
    print(f"State: {state.tuner_state}")
    
    tuner.on_trade_closed({"MFE": 30.0, "MAE": -1.0})
    tuner.on_trade_closed({"MFE": 30.0, "MAE": -1.0}) # Ratio = 60 / 2 = 30 (>= 2.5)
    
    await asyncio.sleep(0.1)
    
    print(f"Scorer weights after recovery: {scorer.dynamic_core_min}, {scorer.macro_weight}, {scorer.micro_weight}, {scorer.vol_weight}")
    print(f"State: {state.tuner_state}")
    
    tuner.stop()

if __name__ == "__main__":
    asyncio.run(test())
