import os
import re

def patch_scorer():
    file_path = 'src/alpha/alpha_scorer.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Imports
    if 'from src.analytics.ml_oracle import MLOracle' not in content:
        content = content.replace('from typing import Dict, Any', 'from typing import Dict, Any\nfrom src.analytics.ml_oracle import MLOracle')

    # 2. Init
    init_target = '''class AlphaScorer:
    def __init__(self):
        self.radar = RegimeRadar()'''
    init_replace = '''class AlphaScorer:
    def __init__(self, oracle: MLOracle = None):
        self.radar = RegimeRadar()
        self.oracle = oracle if oracle else MLOracle()'''
    if init_target in content:
        content = content.replace(init_target, init_replace)

    # 3. Evaluate
    # We will inject the ML logic before the final bounds check.
    eval_target = '''        # Ensure bounds
        buy_score = min(100, max(0, int(buy_score)))
        sell_score = min(100, max(0, int(sell_score)))'''
    eval_replace = '''        # Phase 9: ML Oracle Integration
        ml_prob = await self.oracle.predict(ind)
        if ml_prob > 0.0 and self.oracle.mode == "ACTIVE":
            # ml_prob > 0.5 favors BUY, ml_prob < 0.5 favors SELL
            # We apply a heavy multiplier based on ML conviction
            buy_score *= (ml_prob * 2.0)
            sell_score *= ((1.0 - ml_prob) * 2.0)

        # Ensure bounds
        buy_score = min(100, max(0, int(buy_score)))
        sell_score = min(100, max(0, int(sell_score)))'''
    if eval_target in content:
        content = content.replace(eval_target, eval_replace)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    patch_scorer()
