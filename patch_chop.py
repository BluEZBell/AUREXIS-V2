import re
with open('src/strategy/alpha_harvester.py', 'r', encoding='utf-8') as f:
    content = f.read()

chop_func = '''
    async def calculate_chop_score(self, ind: dict) -> int:
        score = 0
        if not ind:
            return score
        # Extremely tight ranges
        m5_range_10 = ind.get('m5_range_10', 10.0)
        atr_m15 = ind.get('atr_m15', 20.0)
        if m5_range_10 < atr_m15 * 0.4:
            score += 2
        # No EMA expansion
        ema_expansion = ind.get('ema_expansion', False)
        if not ema_expansion:
            score += 1
        # Flat ADX
        adx_m15 = ind.get('adx_m15', 20.0)
        if adx_m15 < 20.0:
            score += 1
        return score

    async def _calculate_conviction'''

content = content.replace('    async def _calculate_conviction', chop_func)

with open('src/strategy/alpha_harvester.py', 'w', encoding='utf-8') as f:
    f.write(content)
