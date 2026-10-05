import asyncio
import logging
import statistics
import math
import MetaTrader5 as mt5
from typing import Tuple
from src.core.config import run_mt5_task; import src.core.config as config

logger = logging.getLogger("dynamic_calibrator")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class DynamicParamStore:
    def __init__(self):
        self.adx_threshold: float = 22.0
        self.volume_multiplier: float = 1.5
        self.atr_baseline: float = 0.0001
        self._lock = asyncio.Lock()

    async def update(self, adx: float, vol: float, atr: float):
        async with self._lock:
            self.adx_threshold = adx
            self.volume_multiplier = vol
            self.atr_baseline = atr

    async def get(self) -> Tuple[float, float, float]:
        async with self._lock:
            return self.adx_threshold, self.volume_multiplier, self.atr_baseline

class DynamicCalibrator:
    def __init__(self, store: DynamicParamStore):
        self.store = store
        self.is_running = False

    async def start(self):
        self.is_running = True
        logger.info("Dynamic Auto-Calibration Engine started.")
        while self.is_running:
            try:
                await self.calibrate()
            except Exception as e:
                logger.error(f"Calibration error: {e}")
            
            # 1 hour = 3600 seconds, broken up to allow cancellation
            for _ in range(360):
                if not self.is_running:
                    break
                await asyncio.sleep(10)

    def stop(self):
        self.is_running = False

    async def calibrate(self):
        await asyncio.sleep(0)  # Non-blocking yield
        
        # Last 24 hours of M15 = 24 * 4 = 96 bars
        # Fetch extra bars for indicator calculations
        num_bars = 150
        rates = await run_mt5_task(mt5.copy_rates_from_pos, config.TRADING_SYMBOL, mt5.TIMEFRAME_M15, 0, num_bars)
        
        if rates is None or len(rates) < 100:
            logger.warning("DynamicCalibrator: Not enough M15 data to calibrate. Using fallbacks.")
            return

        from src.core.math_engine import calc_adx, calc_atr

        import numpy as np
        highs = np.array([float(r['high']) for r in rates])
        lows = np.array([float(r['low']) for r in rates])
        closes = np.array([float(r['close']) for r in rates])
        tick_volumes = [float(r['tick_volume']) for r in rates]

        adx_values = calc_adx(highs, lows, closes, 14)
        atr_values = calc_atr(highs, lows, closes, 14)

        # We want statistics over the last 96 bars
        recent_adx = adx_values[-96:]
        recent_atr = atr_values[-96:]
        recent_vol = tick_volumes[-96:]

        if len(recent_adx) == 0 or len(recent_atr) == 0 or len(recent_vol) == 0:
            return

        # 1. Dynamic_ADX_Threshold
        valid_adx = [x for x in recent_adx if not math.isnan(x)]
        if valid_adx:
            valid_adx.sort()
            idx = int(0.40 * len(valid_adx))
            dynamic_adx = float(valid_adx[idx])
            dynamic_adx = max(15.0, min(30.0, dynamic_adx))
        else:
            dynamic_adx = 22.0

        # 2. Dynamic_Volume_Multiplier
        vol_mean = statistics.mean(recent_vol)
        vol_std = statistics.stdev(recent_vol) if len(recent_vol) > 1 else 0
        if vol_mean > 0:
            dynamic_vol = 1.0 + (vol_std / vol_mean)
        else:
            dynamic_vol = 1.5
        
        dynamic_vol = max(1.2, min(2.5, dynamic_vol))

        # 3. Dynamic_ATR_Baseline
        valid_atr = [x for x in recent_atr if not math.isnan(x)]
        if valid_atr:
            valid_atr.sort()
            # Median
            idx = int(0.50 * len(valid_atr))
            dynamic_atr = float(valid_atr[idx])
        else:
            dynamic_atr = 0.0001

        await self.store.update(dynamic_adx, dynamic_vol, dynamic_atr)
        
        logger.info(f"Calibration Complete - ADX Threshold: {dynamic_adx:.2f}, "
                    f"Volume Multiplier: {dynamic_vol:.2f}x, ATR Baseline: {dynamic_atr:.5f}")
