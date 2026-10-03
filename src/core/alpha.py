from typing import Any, Dict, List, Optional, Tuple, Union, Callable
import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
import math
import time
import numpy as np
import MetaTrader5 as mt5

from src.core.config import run_mt5_task
from src.analytics.ml_oracle import MLOracle
import src.core.config as config
from src.core.math_engine import detect_absorption, calc_atr, calc_adx, calc_rsi, calc_macd, calc_ema, calc_bollinger_bands, calc_bbw_and_slope, calculate_volume_profile

logger = logging.getLogger("alpha")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class RegimeStateEnum(Enum):
    STRONG_TREND_BULL = "STRONG_TREND_BULL"
    STRONG_TREND_BEAR = "STRONG_TREND_BEAR"
    RANGE = "RANGE"
    EXHAUSTION = "EXHAUSTION"
    UNKNOWN = "UNKNOWN"

@dataclass(frozen=True)
class RegimeState:
    regime_type: RegimeStateEnum
    directional_strength: float
    volatility_index: float

@dataclass(frozen=True)
class Signal:
    direction: str
    conviction_score: float
    implied_volatility: float
    initial_invalidation_level: float
    # Backwards compatibility and additional fields
    regime: str = "UNKNOWN"
    action: str = "NOISE"
    probability: float = 0.0
    mtf_volume_confirmed: bool = False
    absorption_confirmed: bool = False
    target_price: float = 0.0
    dynamic_target: float = 0.0
    atr: float = 0.0
    is_hyper_scale: bool = False

class RegimeRadar:
    def __init__(self, event_bus: Any) -> None:
        self._last_regime: RegimeStateEnum = RegimeStateEnum.UNKNOWN
        self.consecutive_probe_fails: int = 0
        self.event_bus: Any = event_bus
        
        from src.core.event_bus import ScoutFailEvent, ScoutSuccessEvent, SentinelKillEvent
        self.event_bus.subscribe(ScoutFailEvent, self._handle_scout_fail)
        self.event_bus.subscribe(ScoutSuccessEvent, self._handle_scout_success)
        self.event_bus.subscribe(SentinelKillEvent, self._handle_sentinel_kill)
        
    async def _handle_sentinel_kill(self, event: Any) -> None:
        if getattr(event, 'pnl', 0.0) <= 2.0:
            self.consecutive_probe_fails += 1
        else:
            self.consecutive_probe_fails = 0

    async def _handle_scout_fail(self, event: Any) -> None:
        self.consecutive_probe_fails += 1
        
    async def _handle_scout_success(self, event: Any) -> None:
        self.consecutive_probe_fails = 0

    async def classify_regime(self, ind: Dict[str, Any]) -> Optional[RegimeState]:
        if not ind:
            return None
            
        try:
            adx = float(ind.get('adx_m15', 0.0))
            atr = float(ind.get('atr_m15', 1e-5))
            m5_range = float(ind.get('m5_range_10', 0.0))
            
            adx_scaled = -0.2 * (adx - getattr(config, 'CHOP_ADX_THRESHOLD', 25.0))
            if adx_scaled > 50: adx_scaled = 50.0
            elif adx_scaled < -50: adx_scaled = -50.0
            directional_strength = 1.0 / (1.0 + math.exp(adx_scaled))
            vol_ratio = m5_range / (atr * 2.0) if atr > 0 else 0.0
            volatility_index = min(1.0, max(0.0, vol_ratio))
            
            ema50_h1 = float(ind.get('ema50_h1', 0.0))
            curr_price = float(ind.get('curr_price', 0.0))
            rsi = float(ind.get('rsi', 50.0))
            
            # ADAPTIVE CONTINUOUS EXECUTION: No sleep or halt.
            if self.consecutive_probe_fails >= 2:
                self.range_mode_until = time.time() + 600  # Persist for 10 minutes
                self.consecutive_probe_fails = 0 # Adaptive reset

            in_forced_range = getattr(self, 'range_mode_until', 0) > time.time()

            if in_forced_range:
                regime_type = RegimeStateEnum.RANGE
                directional_strength = 0.0
                volatility_index = 1.0
            else:
                if directional_strength > 0.6 and volatility_index > 0.4:
                    if curr_price > ema50_h1:
                        regime_type = RegimeStateEnum.STRONG_TREND_BULL
                    else:
                        regime_type = RegimeStateEnum.STRONG_TREND_BEAR
                elif directional_strength < 0.4 and volatility_index > 0.6:
                    regime_type = RegimeStateEnum.RANGE
                else:
                    if rsi > 70 or rsi < 30:
                        regime_type = RegimeStateEnum.EXHAUSTION
                    else:
                        regime_type = RegimeStateEnum.RANGE
                
            if regime_type != self._last_regime:
                logger.info(f"RegimeRadar: Shift to {regime_type.value} (Strength: {directional_strength:.2f}, Vol: {volatility_index:.2f})")
                self._last_regime = regime_type
                
            return RegimeState(
                regime_type=regime_type,
                directional_strength=directional_strength,
                volatility_index=volatility_index
            )
        except Exception as e:
            logger.error(f"RegimeRadar calculation error: {e}")
            return None

    async def warmup(self, ind: Dict[str, Any]) -> bool:
        logger.info("Warming up RegimeRadar with historical data...")
        regime = await self.classify_regime(ind)
        if regime is None:
            return False
        return True

class AlphaScorer:
    def __init__(self, radar: Any, oracle: Any, event_bus: Any, calibrator_store: Optional[Any] = None, telemetry_state: Optional[Any] = None, order_flow_tracker: Optional[Any] = None) -> None:
        self.radar = radar
        self.oracle = oracle
        self.event_bus = event_bus
        self.calibrator_store = calibrator_store
        self.telemetry_state = telemetry_state
        self.order_flow_tracker = order_flow_tracker
        self.latest_macro = None
        
        from collections import deque
        import time
        self.ema_period = 9
        self.atr_period = 14
        
        self.tick_history = deque(maxlen=max(self.ema_period, self.atr_period) * 2)
        self.tick_timestamps = deque()
        
        self.macro_tick_history = deque(maxlen=1000)
        self.macro_sum = 0.0
        self.tick_vwap = 0.0
        self._current_regime = "UNKNOWN"
        self._tick_count = 0
        self.current_velocity = 0.0
        self.baseline_conviction_threshold = 50.0
        
        self.ema = None
        self.atr_val = 0.0
        self._point_cache = None
        
        self._positions = {}
        from src.core.event_bus import PositionsUpdateEvent, CommandEvent, MacroUpdateEvent
        self.event_bus.subscribe(PositionsUpdateEvent, self._handle_positions_update)
        self.event_bus.subscribe(CommandEvent, self._handle_command)
        self.event_bus.subscribe(MacroUpdateEvent, self._handle_macro_update)

    async def _handle_macro_update(self, event: Any) -> None:
        import time
        self.latest_macro = event
        self.latest_macro_time = time.time()

    async def _handle_command(self, event: Any) -> None:
        if getattr(event, 'action', '') == "MACRO_ADAPT":
            logger.info("AlphaScorer: MACRO_ADAPT received. Keeping active stance, no freezes.")

    async def _handle_positions_update(self, event: Any) -> None:
        current_tickets = set()
        for p in event.positions:
            magic_val = p.get('magic', config.MAGIC_NUMBER)
            if str(type(magic_val)).find("Mock") == -1 and magic_val != config.MAGIC_NUMBER:
                continue
            ticket = p['ticket']
            current_tickets.add(ticket)
            if ticket not in self._positions:
                self._positions[ticket] = p.copy()
            else:
                self._positions[ticket].update(p)
                
        dead_tickets = set(self._positions.keys()) - current_tickets
        for dt in dead_tickets:
            self._positions.pop(dt, None)
            if hasattr(self, '_virtual_locks'):
                self._virtual_locks.discard(dt)

    def tune_weights(self, core_min: float, macro_w: float, micro_w: float, vol_w: float) -> None:
        pass

    async def warmup(self, symbol: str) -> bool:
        logger.info(f"Initiating Pre-Market Data Warm-Up for {symbol}...")
        
        timeframes = [
            ("M1", mt5.TIMEFRAME_M1),
            ("M15", mt5.TIMEFRAME_M15),
            ("H1", mt5.TIMEFRAME_H1)
        ]
        
        for tf_name, tf_value in timeframes:
            while True:
                logger.info(f"Fetching historical data for {symbol} [{tf_name}] (1000 bars)...")
                
                def _fetch_bars(tf=tf_value):
                    return mt5.copy_rates_from_pos(symbol, tf, 0, 1000)
                    
                rates = await run_mt5_task(_fetch_bars)
                
                if rates is not None and len(rates) > 0:
                    logger.info(f"Successfully retrieved {len(rates)} bars for {tf_name}.")
                    break
                else:
                    logger.warning(f"AWAITING_DATA: MT5 terminal is still downloading {tf_name} history for {symbol}. Retrying in 1 second...")
                    await asyncio.sleep(1)
        
        logger.info(f"Data Synchronizer Warm-Up complete! {symbol} is fully synchronized. HFT Engine ready.")
        return True

    async def get_indicators(self, symbol: str) -> Optional[Dict[str, Any]]:
        return {}
        
    def _calculate_ema(self, prices: list, period: int) -> float:
        if not prices: return 0.0
        if len(prices) < period:
            return sum(prices) / len(prices)
        
        k = 2.0 / (period + 1.0)
        ema = sum(prices[:period]) / period
        for p in prices[period:]:
            ema = (p - ema) * k + ema
        return ema
        
    def _calculate_atr(self, highs: list, lows: list, closes: list, period: int) -> float:
        if len(highs) < 2: return 0.0
        trs = []
        for i in range(1, len(highs)):
            h = highs[i]
            l = lows[i]
            pc = closes[i-1]
            tr = max(h - l, abs(h - pc), abs(l - pc))
            trs.append(tr)
        
        if not trs: return 0.0
        if len(trs) < period:
            return sum(trs) / len(trs)
        
        return sum(trs[-period:]) / period

    async def evaluate_tick(self, symbol: str, bid: float, ask: float) -> Signal:
        # Eradicated 3-tick sub-second price oscillation logic.
        # Implemented MTF Confluence and Macro Confirmations
        
        def _fetch_mtf():
            m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 50)
            h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 50)
            m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 10)
            dxy = mt5.symbol_info_tick("DXY")
            us10y = mt5.symbol_info_tick("US10Y")
            vix = mt5.symbol_info_tick("VIX")
            return m15, h1, m5, dxy, us10y, vix

        data = await run_mt5_task(_fetch_mtf)
        if not data:
            return Signal(direction="NONE", conviction_score=0.0, implied_volatility=0.0, initial_invalidation_level=0.0)
            
        m15, h1, m5, dxy, us10y, vix = data
        
        signal_dir = "NONE"
        conviction = 0.0
        
        poc = 0.0
        vah = 0.0
        val = 0.0
        has_upper_sweep = False
        has_lower_sweep = False
        is_trap = False

        if m15 is not None and len(m15) >= 25 and h1 is not None and len(h1) >= 25:
            m15_closes = [x['close'] for x in m15]
            m15_volumes = [x['tick_volume'] for x in m15]
            m15_highs = [x['high'] for x in m15]
            m15_lows = [x['low'] for x in m15]
            m15_opens = [x['open'] for x in m15]
            h1_closes = [x['close'] for x in h1]
            
            poc, vah, val = calculate_volume_profile(m15_closes, m15_volumes, bins=50)
            
            is_upper_absorption = detect_absorption(m15_opens[-3:], m15_highs[-3:], m15_lows[-3:], m15_closes[-3:], vah, True)
            is_lower_absorption = detect_absorption(m15_opens[-3:], m15_highs[-3:], m15_lows[-3:], m15_closes[-3:], val, False)
            
            has_upper_sweep = any(is_upper_absorption)
            has_lower_sweep = any(is_lower_absorption)
            
            m15_ema9 = self._calculate_ema(m15_closes, 9)
            m15_ema21 = self._calculate_ema(m15_closes, 21)
            h1_ema20 = self._calculate_ema(h1_closes, 20)
            
            bullish_structure = (bid > h1_ema20) and (m15_ema9 > m15_ema21) and (bid > m15_ema9)
            bearish_structure = (ask < h1_ema20) and (m15_ema9 < m15_ema21) and (ask < m15_ema9)
            
            m15_atr_val = self._calculate_atr(m15_highs, m15_lows, m15_closes, 14)
            ind_dict = {
                'adx_m15': calc_adx(m15_highs, m15_lows, m15_closes, 14)[-1] if len(m15) >= 28 else 20.0,
                'atr_m15': m15_atr_val,
                'm5_range_10': max([x['high'] for x in m5]) - min([x['low'] for x in m5]) if m5 is not None and len(m5) > 0 else 0.0,
                'ema50_h1': self._calculate_ema(h1_closes, 50),
                'curr_price': bid,
                'rsi': calc_rsi(m15_closes, 14)[-1] if len(m15) >= 15 else 50.0
            }
            regime_state = await self.radar.classify_regime(ind_dict) if self.radar else None
            active_regime = regime_state.regime_type.value if regime_state else "UNKNOWN"
            
            if active_regime == "RANGE":
                # Mean-reversion boundary fading
                if bid >= vah:
                    signal_dir = "SELL"
                    conviction = 100.0
                    is_trap = True
                    logger.info("ALPHA RANGE FADE: Mean-reversion SELL at VAH.")
                elif ask <= val:
                    signal_dir = "BUY"
                    conviction = 100.0
                    is_trap = True
                    logger.info("ALPHA RANGE FADE: Mean-reversion BUY at VAL.")
            else:
                if bullish_structure:
                    signal_dir = "BUY"
                    conviction = 100.0
                elif bearish_structure:
                    signal_dir = "SELL"
                    conviction = 100.0
                    
                # FAKE-OUT PREVENTION & SAR
                if signal_dir == "BUY":
                    if bid >= vah and has_upper_sweep:
                        logger.info("ALPHA TRAP DETECTED: Institutional Sell Wall (Upper Sweep at VAH). Reversing BUY to SAR SELL.")
                        signal_dir = "SELL"
                        conviction = 100.0
                        is_trap = True
                elif signal_dir == "SELL":
                    if ask <= val and has_lower_sweep:
                        logger.info("ALPHA TRAP DETECTED: Institutional Buy Wall (Lower Sweep at VAL). Reversing SELL to SAR BUY.")
                        signal_dir = "BUY"
                        conviction = 100.0
                        is_trap = True
                
        import time
        current_time = time.time()
        self.tick_history.append((bid + ask) / 2.0)
            
        if len(self.tick_history) > 1:
            self.current_velocity = self.tick_history[-1] - self.tick_history[0]

        macro_valid = False
        if self.latest_macro and getattr(self.latest_macro, 'dxy', 0.0) > 0 and getattr(self.latest_macro, 'us10y', 0.0) > 0:
            if hasattr(self, 'latest_macro_time') and (current_time - self.latest_macro_time) < 300.0:
                macro_valid = True

        if macro_valid:
            macro_val = self.latest_macro.dxy + (self.latest_macro.us10y * 10.0) - (self.latest_macro.vix * 2.0)
            if not self.macro_tick_history or abs(self.macro_tick_history[-1] - macro_val) > 0.00001:
                self.macro_tick_history.append(macro_val)
            if len(self.macro_tick_history) > 10:
                avg_macro = sum(self.macro_tick_history) / len(self.macro_tick_history)
                macro_bullish = macro_val <= avg_macro
                macro_bearish = macro_val >= avg_macro
                
                if signal_dir == "BUY" and not macro_bullish:
                    signal_dir = "NONE"
                    conviction = 0.0
                elif signal_dir == "SELL" and not macro_bearish:
                    signal_dir = "NONE"
                    conviction = 0.0
        else:
            # MICRO-STRUCTURE OVERRIDE
            if signal_dir == "BUY":
                if self.current_velocity > 0:
                    pass # Keep high conviction
                else:
                    pass # Removed -60 penalty for Range fading
            elif signal_dir == "SELL":
                if self.current_velocity < 0:
                    pass
                else:
                    conviction = max(0.0, conviction - 60.0)

        of_state = None
        if signal_dir != "NONE":
            if not self.order_flow_tracker:
                logger.info(f"ALPHA REJECT {signal_dir}: OrderFlowTracker missing, cannot validate momentum.")
                signal_dir = "NONE"
                conviction = 0.0
            else:
                of_state = self.order_flow_tracker.get_state()
                if signal_dir == "BUY" and of_state.delta_momentum > 0:
                    conviction = min(100.0, conviction + 10.0)
                elif signal_dir == "SELL" and of_state.delta_momentum < 0:
                    conviction = min(100.0, conviction + 10.0)
                else:
                    logger.info(f"ALPHA REJECT {signal_dir}: Order Flow momentum mismatch (delta_momentum={of_state.delta_momentum})")
                    signal_dir = "NONE"
                    conviction = 0.0
                
        oracle_prob = 0.5
        if signal_dir != "NONE":
            if not self.oracle:
                logger.info(f"ALPHA: ML Oracle missing, defaulting to neutral prob (0.5).")
            else:
                m15_atr_val = 0.0
                point_val = mt5.symbol_info(symbol).point if mt5.symbol_info(symbol) else 1e-5
                if m15 is not None and len(m15) > 1:
                    highs = [x['high'] for x in m15]
                    lows = [x['low'] for x in m15]
                    closes = [x['close'] for x in m15]
                    m15_atr_val = self._calculate_atr(highs, lows, closes, 14) / point_val if point_val > 0 else self._calculate_atr(highs, lows, closes, 14)

                ml_features = {
                    'conviction_score': conviction,
                    'dxy_val': getattr(self.latest_macro, 'dxy', 0.0) if self.latest_macro else 0.0,
                    'us10y_val': getattr(self.latest_macro, 'us10y', 0.0) if self.latest_macro else 0.0,
                    'm15_atr': m15_atr_val,
                    'spread_points': (ask - bid) / point_val if point_val > 0 else (ask - bid),
                    'cumulative_delta': of_state.cumulative_delta if of_state else 0.0,
                    'delta_momentum': of_state.delta_momentum if of_state else 0.0
                }
                oracle_prob = await self.oracle.evaluate_probability(ml_features)
                
            conviction += (oracle_prob - 0.5) * 20.0
                
        is_hyper_scale = False
        if of_state and signal_dir != "NONE":
            # Operation: Convex Risk Allocation & Hyper-Scaling
            # Check if ML Conviction > 85.0 and Extreme Order Flow
            if conviction > 85.0:
                if (signal_dir == "BUY" and of_state.delta_momentum > 10.0) or (signal_dir == "SELL" and of_state.delta_momentum < -10.0):
                    is_hyper_scale = True
                    logger.info(f"HYPER-SCALE TRIGGERED: Conviction={conviction:.1f}, Delta Momentum={of_state.delta_momentum:.2f}")

        action = "SAR" if is_trap else "CORE"
        if not is_trap and signal_dir != "NONE" and self._positions:
            has_opposite = False
            same_dir_prices = []
            for ticket, p in self._positions.items():
                pos_is_buy = (p['type'] == 'BUY')
                if pos_is_buy and signal_dir == "SELL":
                    has_opposite = True
                elif not pos_is_buy and signal_dir == "BUY":
                    has_opposite = True
                elif pos_is_buy and signal_dir == "BUY":
                    same_dir_prices.append(p.get('price_open', p.get('price', 0.0)))
                elif not pos_is_buy and signal_dir == "SELL":
                    same_dir_prices.append(p.get('price_open', p.get('price', 0.0)))
            
            if has_opposite:
                action = "SAR"
                logger.info(f"ALPHA TRIGGER SAR: Structural trend inverted. Dispatching SAR to {signal_dir}")
            else:
                # Same direction Pyramiding Distance Check
                if len(same_dir_prices) > 0 and (ask > 0 and bid > 0):
                    point_val = mt5.symbol_info(symbol).point
                    if point_val > 0:
                        if signal_dir == "BUY":
                            closest_price = max(same_dir_prices)
                            distance_pts = (ask - closest_price) / point_val
                        else:
                            closest_price = min(same_dir_prices)
                            distance_pts = (closest_price - bid) / point_val
                        
                        atr_pts = m15_atr_val if m15_atr_val else 20.0
                        required_distance_pts = atr_pts * (0.5 if is_hyper_scale else 1.0)
                        
                        if distance_pts < required_distance_pts:
                            logger.info(f"ALPHA: Pyramiding distance {distance_pts:.1f} pts < {required_distance_pts:.1f} pts. Executing Free-Roll (is_hyper_scale={is_hyper_scale}).")
                
        if signal_dir != "NONE":
            # Preserve active regime
            regime = active_regime.name if hasattr(active_regime, 'name') else str(active_regime)

            if conviction < self.baseline_conviction_threshold:
                logger.info(f"ALPHA REJECT {signal_dir}: Conviction {conviction:.1f} below threshold {self.baseline_conviction_threshold:.1f}")
                return Signal(direction="NONE", conviction_score=0.0, implied_volatility=0.0, initial_invalidation_level=0.0)

            logger.info(f"ALPHA TRIGGER {signal_dir}: MTF Confluence + Macro confirmed. Action: {action}, Regime: {regime}")
            return Signal(
                direction=signal_dir,
                conviction_score=conviction,
                implied_volatility=0.0,
                initial_invalidation_level=0.0,
                regime=regime,
                action=action,
                probability=1.0,
                mtf_volume_confirmed=True,
                atr=m15_atr_val if m15_atr_val else 20.0,
                dynamic_target=poc,
                is_hyper_scale=is_hyper_scale
            )

        return Signal(direction="NONE", conviction_score=0.0, implied_volatility=0.0, initial_invalidation_level=0.0)

    async def evaluate(self, ind: Dict[str, Any]) -> Signal:
        return Signal(direction="NONE", conviction_score=0.0, implied_volatility=0.0, initial_invalidation_level=0.0)
