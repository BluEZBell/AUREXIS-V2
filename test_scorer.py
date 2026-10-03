import asyncio
from src.core.alpha import AlphaScorer
from src.core.alpha import RegimeRadar
from unittest.mock import MagicMock

async def main():
    radar = RegimeRadar(MagicMock())
    scorer = AlphaScorer(radar, MagicMock(), MagicMock())
    
    ind = {
        'curr_price': 100.0,
        'ema20_m15': 100.0,
        'bb_upper': 99.0,
        'bb_lower': 98.0,
        'atr_m15': 1.0,
        'm5_open': [100.0],
        'm5_high': [101.0],
        'm5_low': [99.0],
        'm5_close': [100.0],
    }
    
    result = await scorer.evaluate(ind)
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
