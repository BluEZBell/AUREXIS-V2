from typing import Any, Dict, List, Optional, Tuple, Union, Callable
import asyncio
import time
import datetime
import numpy as np
import MetaTrader5 as mt5
from src.core.event_bus import EventBus, SignalEvent, OrderEvent, ErrorEvent, PositionsUpdateEvent, TickEvent, StructuralTrendEvent
from src.core.telemetry import TelemetryLogger
from src.core.config import MT5_TERMINAL_PATH, MAGIC_NUMBER, setup_logger, run_mt5_task
import src.core.config as config
from src.execution.risk_manager import RiskManager

logger = setup_logger("execution_bridge")

def resolve_and_select_symbol(base_symbol: str) -> str:
    symbols = mt5.symbols_get()
    if symbols:
        gold_keywords = ["XAUUSD", "GOLD"]
        # Ensure we pick a fully tradable symbol if available
        for s in symbols:
            name_upper = s.name.upper()
            if any(k in name_upper for k in gold_keywords):
                if s.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL or s.trade_mode == 4:
                    mt5.symbol_select(s.name, True)
                    if mt5.symbol_info_tick(s.name) is not None:
                        return s.name
                        
        # Fallback to any matched keyword symbol that provides ticks
        for s in symbols:
            name_upper = s.name.upper()
            if any(k in name_upper for k in gold_keywords):
                mt5.symbol_select(s.name, True)
                if mt5.symbol_info_tick(s.name) is not None:
                    return s.name

    return base_symbol

from src.execution.profiler import ExecutionProfiler
class MT5Bridge:
    def __init__(self, event_bus: EventBus, risk_manager: 'Optional[RiskManager]' = None, calibrator_store=None, telemetry_logger: 'Optional[TelemetryLogger]' = None, telemetry_state=None):
        self.calibrator_store = calibrator_store
        self.event_bus = event_bus
        self.risk_manager = risk_manager
        self.telemetry_logger = telemetry_logger
        self.telemetry_state = telemetry_state
        self.terminal_path = MT5_TERMINAL_PATH
        from src.core.dynamic_params import DynamicParamStore
        self.param_store = DynamicParamStore()
        from src.core.event_bus import CommandEvent
        self.event_bus.subscribe(SignalEvent, self.process_signal)
        self.event_bus.subscribe(OrderEvent, self.process_order_request)
        self.event_bus.subscribe(ErrorEvent, self.handle_error)
        self.event_bus.subscribe(CommandEvent, self.process_command)
        
        # Lock removed for HFT concurrent execution
        self._last_order_time = 0.0
        self._last_stop_loss_time = 0.0
        self._last_stop_loss_price = 0.0
        self._panic_halt = False
        self._start_equity = None
        self._current_day = None
        self._latest_m15_trend = "NEUTRAL"
        self._latest_h1_trend = "NEUTRAL"
        self._latest_m15_atr = 0.0
        self._known_tickets = set()
        self.is_connected = True
        self.profiler = ExecutionProfiler()

    async def initialize(self) -> bool:
        init_args = {}
        if self.terminal_path:
            init_args['path'] = self.terminal_path
            
        initialized = await asyncio.to_thread(mt5.initialize, **init_args)
        if not initialized:
            err_details = await asyncio.to_thread(mt5.last_error)
            logger.critical(f"Failed to initialize MetaTrader 5! Error: {err_details}")
            from src.core.event_bus import ErrorEvent
            await self.event_bus.publish(ErrorEvent("MT5Bridge", f"SYSTEM ERROR: MT5 IPC Init Failed. {err_details}", critical=True))
            return False
            
        acc_info = await asyncio.to_thread(mt5.account_info)
        active_login = getattr(acc_info, 'login', None)
        env_login_str = getattr(config, 'MT5_LOGIN', "")
        
        skip_login = False
        env_login = None
        
        env_login_str = str(env_login_str).strip()
        if env_login_str in ["123456", "12345678", "0", ""]:
            env_login_str = None

        if not env_login_str:
            skip_login = True
        else:
            try:
                env_login = int(env_login_str)
                if active_login == env_login:
                    skip_login = True
            except ValueError:
                skip_login = True
                
        if skip_login:
            logger.info(f"Seamlessly attached to active MT5 session [{active_login}]")
        else:
            login_args = {"login": env_login}
            pwd = getattr(config, 'MT5_PASSWORD', "")
            srv = getattr(config, 'MT5_SERVER', "")
            if pwd:
                login_args["password"] = pwd
            if srv:
                login_args["server"] = srv
                
            login_success = await asyncio.to_thread(mt5.login, **login_args)
            if login_success:
                logger.info(f"Enforced .env credentials and logged into [{env_login}]")
            else:
                err = await asyncio.to_thread(mt5.last_error)
                logger.error(f"MT5 login failed for {env_login}. Error: {err}")
                if err and (err[0] == -6 or "Authorization failed" in str(err)):
                    from src.core.exceptions import ConfigError
                    raise ConfigError("MT5 Authorization Failed. Please verify your .env credentials or leave MT5_LOGIN blank to use the active terminal session.")
                return False

        logger.info(f"MT5 Bridge initialized to {self.terminal_path}")
        
        t_info = await asyncio.to_thread(mt5.terminal_info)
        if t_info and not getattr(t_info, 'trade_allowed', False):
            logger.critical("MT5 ALGO TRADING DISABLED: Turn on the 'Algo Trading' button in the MT5 Terminal")
            
        original = getattr(config, 'TRADING_SYMBOL', 'GOLD')
        res = await asyncio.to_thread(mt5.symbol_select, original, True)
        logger.info(f"Explicit mt5.symbol_select({original}, True) result: {res}")
        
        def _resolve_ts():
            return resolve_and_select_symbol(original)
        
        config.TRADING_SYMBOL = await asyncio.to_thread(_resolve_ts)
        msg = f"> RESOLVED TRADING SYMBOL: {original} -> {config.TRADING_SYMBOL}"
        logger.info(msg)
        
        from src.core.event_bus import LogEvent
        await self.event_bus.publish(LogEvent(message=msg))
        return True
            


    async def start_streams(self):
        asyncio.create_task(self.start_position_broadcaster())
        asyncio.create_task(self.start_tick_stream())
        asyncio.create_task(self.start_structure_stream())
        asyncio.create_task(self.run_connection_watchdog())

    async def run_connection_watchdog(self) -> None:
        while True:
            try:
                def _check_connected():
                    t_info = mt5.terminal_info()
                    return t_info is not None and t_info.connected
                
                connected = await run_mt5_task(_check_connected)
                if connected and not self.is_connected:
                    self.is_connected = True
                    logger.info("MT5 Connection Watchdog: Connection restored to Broker Server.")
                    if getattr(self, 'telemetry_state', None):
                        self.telemetry_state.broker_online = True
                elif not connected and self.is_connected:
                    self.is_connected = False
                    logger.critical("MT5 Connection Watchdog: BROKER CONNECTION DROPPED. Signals suppressed.")
                    if getattr(self, 'telemetry_state', None):
                        self.telemetry_state.broker_online = False
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in connection watchdog: {e}")
            await asyncio.sleep(1.0)

    async def get_live_balance(self) -> float:
        def _fetch():
            acc = mt5.account_info()
            if not acc:
                init_args = {}
                if self.terminal_path:
                    init_args['path'] = self.terminal_path
                mt5.initialize(**init_args)
                acc = mt5.account_info()
            if acc:
                return float(acc.balance)
            raise RuntimeError("MT5Bridge failed to fetch live account balance. Terminal disconnected.")
        return await run_mt5_task(_fetch)

    async def start_tick_stream(self):
        while True:
            try:
                def _get_tick():
                    mt5.symbol_select(config.TRADING_SYMBOL, True)
                    return mt5.symbol_info_tick(config.TRADING_SYMBOL)
                tick = await run_mt5_task(_get_tick)
                if tick is not None:
                    # Prefer volume_real if available, else fallback to volume
                    tick_vol = getattr(tick, 'volume_real', getattr(tick, 'volume', 1.0))
                    event = TickEvent(
                        symbol=config.TRADING_SYMBOL,
                        time=tick.time,
                        bid=tick.bid,
                        ask=tick.ask,
                        volume=float(tick_vol)
                    )
                    await self.event_bus.publish(event)
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Loop Error in tick stream")
                await asyncio.sleep(0.5)

    async def start_structure_stream(self):
        while True:
            try:
                def _get_rates():
                    m5 = mt5.copy_rates_from_pos(config.TRADING_SYMBOL, mt5.TIMEFRAME_M5, 0, 25)
                    m15 = mt5.copy_rates_from_pos(config.TRADING_SYMBOL, mt5.TIMEFRAME_M15, 0, 200)
                    h1 = mt5.copy_rates_from_pos(config.TRADING_SYMBOL, mt5.TIMEFRAME_H1, 0, 200)
                    return m5, m15, h1
                
                m5_rates, m15_rates, h1_rates = await run_mt5_task(_get_rates)
                
                if m15_rates is not None and len(m15_rates) >= 200 and h1_rates is not None and len(h1_rates) >= 200:
                    m15_closes = np.array([x['close'] for x in m15_rates])
                    h1_closes = np.array([x['close'] for x in h1_rates])
                    
                    m15_close = m15_closes[-1]
                    h1_close = h1_closes[-1]
                    
                    from src.core.math_engine import calc_ema, calc_rsi, calc_adx
                    
                    # Compute ATR early to use it for structure breaks and dynamic bodies
                    point = mt5.symbol_info(config.TRADING_SYMBOL).point
                    atr_sum = 0.0
                    for i in range(1, min(21, len(m15_rates))):
                        high = m15_rates[-i]['high']
                        low = m15_rates[-i]['low']
                        prev_close = m15_rates[-i-1]['close']
                        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                        atr_sum += tr
                    atr = atr_sum / 20.0 if atr_sum > 0 else point
                    atr_points = atr / point
                    self._latest_m15_atr = atr_points
                    
                    # M15/M5 Micro-Confirmation and Anti-Bounce
                    forming_m15 = m15_rates[-1]
                    forming_m5 = m5_rates[-1] if m5_rates is not None and len(m5_rates) > 0 else forming_m15
                    
                    m15_range = max(float(forming_m15['high']) - float(forming_m15['low']), point)
                    
                    min_m15_body = atr * 0.12
                    min_m5_body = atr * 0.14
                    
                    m15_close_near_low = (float(forming_m15['close']) - float(forming_m15['low'])) <= (m15_range * 0.45)
                    m5_is_bearish = float(forming_m5['close']) <= float(forming_m5['open'])
                    
                    m15_body = float(forming_m15['close']) - float(forming_m15['open'])
                    m5_body = float(forming_m5['close']) - float(forming_m5['open'])
                    m15_bearish_body_ok = (m15_body <= -min_m15_body) or (m15_body < 0 and m5_body <= -min_m5_body)
                    
                    m15_bearish_candle = bool(m15_bearish_body_ok and m5_is_bearish and m15_close_near_low)
                    
                    m15_close_near_high = (float(forming_m15['high']) - float(forming_m15['close'])) <= (m15_range * 0.45)
                    m5_is_bullish = float(forming_m5['close']) >= float(forming_m5['open'])
                    m15_bullish_body_ok = (m15_body >= min_m15_body) or (m15_body > 0 and m5_body >= min_m5_body)
                    
                    m15_bullish_candle = bool(m15_bullish_body_ok and m5_is_bullish and m15_close_near_high)
                    
                    # Use strictly closed candles for structural EMA and ADX to prevent mid-candle flickering
                    m15_closes_closed = m15_closes[:-1]
                    h1_closes_closed = h1_closes[:-1]
                    m15_rates_closed = m15_rates[:-1]
                    
                    m15_ema9_closed = calc_ema(m15_closes_closed, 9)[-1]
                    m15_ema20 = calc_ema(m15_closes_closed, 20)[-1]
                    m15_ema50 = calc_ema(m15_closes_closed, 50)[-1]
                    h1_ema9_closed = calc_ema(h1_closes_closed, 9)[-1]
                    h1_ema20 = calc_ema(h1_closes_closed, 20)[-1]
                    h1_ema50 = calc_ema(h1_closes_closed, 50)[-1]
                    
                    if m5_rates is not None and len(m5_rates) >= 20:
                        m5_closes = np.array([x['close'] for x in m5_rates])
                        m5_ema9 = calc_ema(m5_closes, 9)[-1]
                        m5_ema20 = calc_ema(m5_closes, 20)[-1]
                        m5_bull_trend = bool(m5_closes[-1] > m5_ema20)
                        m5_bear_trend = bool(m5_closes[-1] < m5_ema20)
                    else:
                        m5_ema9 = m15_ema9_closed
                        m5_bull_trend = bool(m15_closes[-1] > m15_ema20)
                        m5_bear_trend = bool(m15_closes[-1] < m15_ema20)
                        
                    m15_highs_closed = np.array([x['high'] for x in m15_rates_closed])
                    m15_lows_closed = np.array([x['low'] for x in m15_rates_closed])
                    
                    recent_12_low = float(np.min(m15_lows_closed[-12:])) if len(m15_lows_closed) >= 12 else float(np.min(m15_lows_closed))
                    recent_12_high = float(np.max(m15_highs_closed[-12:])) if len(m15_highs_closed) >= 12 else float(np.max(m15_highs_closed))
                    recent_6_high = float(np.max(m15_highs_closed[-6:])) if len(m15_highs_closed) >= 6 else float(np.max(m15_highs_closed))
                    recent_6_low = float(np.min(m15_lows_closed[-6:])) if len(m15_lows_closed) >= 6 else float(np.min(m15_lows_closed))
                    
                    bullish_structure_reversal = (recent_6_high > m15_ema20 + (atr * 0.4)) and (float(forming_m15['low']) > recent_12_low + (atr * 0.5))
                    bearish_structure_reversal = (recent_6_low < m15_ema20 - (atr * 0.4)) and (float(forming_m15['high']) < recent_12_high - (atr * 0.5))
                    
                    m15_last_closed = m15_closes_closed[-1]
                    h1_last_closed = h1_closes_closed[-1]
                    
                    m5_strong_bull = m5_bull_trend and (float(forming_m5['close']) > float(forming_m5['open']) + min_m5_body)
                    m5_strong_bear = m5_bear_trend and (float(forming_m5['close']) < float(forming_m5['open']) - min_m5_body)
                    live_price_above_m15_ema20 = float(forming_m15['close']) > m15_ema20 and (m15_last_closed > m15_ema20 or float(forming_m15['close']) > m15_ema20 + (atr * 0.15))
                    live_price_below_m15_ema20 = float(forming_m15['close']) < m15_ema20 and (m15_last_closed < m15_ema20 or float(forming_m15['close']) < m15_ema20 - (atr * 0.15))
                    
                    ema20_sloping_up = m15_ema20 > m15_ema50 or m15_ema9_closed >= m15_ema20
                    ema20_sloping_down = m15_ema20 < m15_ema50 or m15_ema9_closed <= m15_ema20

                    # Calculate ADX early for Regime Filter
                    m15_highs_for_adx = np.array([x['high'] for x in m15_rates_closed])
                    m15_lows_for_adx = np.array([x['low'] for x in m15_rates_closed])
                    m15_adx_temp = calc_adx(m15_highs_for_adx, m15_lows_for_adx, m15_closes_closed, 14)[-1]

                    dyn_adx = 22.0
                    if getattr(self, 'calibrator_store', None):
                        try:
                            dyn_adx, _, _ = await self.calibrator_store.get()
                        except Exception:
                            pass
                            
                    buffer = atr * 0.15
                    if m15_adx_temp < dyn_adx:
                        m15_trend = "NEUTRAL"
                    else:
                        if m15_ema20 > m15_ema50 + buffer:
                            m15_trend = "BULLISH"
                        elif m15_ema50 > m15_ema20 + buffer:
                            m15_trend = "BEARISH"
                        else:
                            m15_trend = "NEUTRAL"
                        
                    if h1_last_closed > h1_ema20 and (h1_ema20 > h1_ema50 or h1_ema9_closed >= h1_ema20):
                        h1_trend = "BULLISH"
                    elif h1_last_closed < h1_ema20 and (h1_ema20 < h1_ema50 or h1_ema9_closed <= h1_ema20):
                        h1_trend = "BEARISH"
                    else:
                        h1_trend = "NEUTRAL"
                    
                    if getattr(self, "_latest_m15_trend", None) and self._latest_m15_trend != m15_trend:
                        await self._log_and_publish(f"STRUCTURAL SHIFT: M15 Trend changed from {self._latest_m15_trend} to {m15_trend}", "info")
                    if getattr(self, "_latest_h1_trend", None) and self._latest_h1_trend != h1_trend:
                        await self._log_and_publish(f"STRUCTURAL SHIFT: H1 Trend changed from {self._latest_h1_trend} to {h1_trend}", "info")
                    self._latest_m15_trend = m15_trend
                    self._latest_h1_trend = h1_trend
                    
                    # [Y-Axis Tuning] Calculate Distance from Mean
                    symbol_info = await run_mt5_task(mt5.symbol_info, config.TRADING_SYMBOL)
                    if symbol_info:
                        point = symbol_info.point
                    m15_dist = (forming_m15['close'] - m15_ema20) / point
                    h1_dist = (h1_closes[-1] - h1_ema20) / point
                    m15_distance_z_score = m15_dist / atr_points if atr_points > 0 else 0.0
                    
                    m15_rsi = calc_rsi(m15_closes, 14)[-1]
                    
                    m15_highs = np.array([x['high'] for x in m15_rates_closed])
                    m15_lows = np.array([x['low'] for x in m15_rates_closed])
                    m15_adx = calc_adx(m15_highs, m15_lows, m15_closes_closed, 14)[-1]
                    
                    if len(m15_lows) >= 8:
                        recent_low = float(np.min(m15_lows[-8:]))
                        recent_high = float(np.max(m15_highs[-8:]))
                        
                        if m15_trend == "BEARISH" and float(forming_m15['close']) <= recent_low + (atr * 0.10) and m15_distance_z_score < -0.9 and m15_rsi < 32.0:
                            m15_distance_z_score = min(m15_distance_z_score, -1.6)
                        elif m15_trend == "BULLISH" and float(forming_m15['close']) >= recent_high - (atr * 0.10) and m15_distance_z_score > 0.9 and m15_rsi > 68.0:
                            m15_distance_z_score = max(m15_distance_z_score, 1.6)
                    
                    try:
                        candle_open_time = int(forming_m15['time']) if 'time' in forming_m15.dtype.names else (int(time.time()) // 900) * 900
                    except (KeyError, IndexError, ValueError, AttributeError):
                        candle_open_time = (int(time.time()) // 900) * 900

                    from src.core.math_engine import calculate_volume_profile
                    if m5_rates is not None and len(m5_rates) > 0:
                        m5_closes_for_poc = np.array([x['close'] for x in m5_rates])
                        m5_vols_for_poc = np.array([x['tick_volume'] if 'tick_volume' in m5_rates.dtype.names else x['real_volume'] for x in m5_rates])
                        poc, vah, val = calculate_volume_profile(m5_closes_for_poc, m5_vols_for_poc)
                    else:
                        poc = 0.0
                        
                    event = StructuralTrendEvent(
                        symbol=config.TRADING_SYMBOL,
                        m15_trend=m15_trend,
                        h1_trend=h1_trend,
                        m15_close=m15_close,
                        time=candle_open_time,
                        m15_distance=m15_dist,
                        h1_distance=h1_dist,
                        m15_distance_z_score=m15_distance_z_score,
                        m15_atr=float(atr_points),
                        m15_rsi=float(m15_rsi),
                        m15_adx=float(m15_adx),
                        m15_bullish_candle=m15_bullish_candle,
                        m15_bearish_candle=m15_bearish_candle,
                        hyper_conservative=self.risk_manager.is_hyper_conservative,
                        poc=float(poc)
                    )
                    await self.event_bus.publish(event)
                
                await asyncio.sleep(0.5) # Non-blocking yield
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Loop Error in structure stream")
                await asyncio.sleep(0.5)

    async def _log_and_publish(self, message: str, level: str = "warning"):
        if level == "warning":
            logger.warning(message)
        elif level == "info":
            logger.info(message)
        elif level == "error":
            logger.error(message)
        from src.core.event_bus import LogEvent
        await self.event_bus.publish(LogEvent(message))

    async def start_position_broadcaster(self):
        while True:
            try:
                def _get_positions():
                    return mt5.positions_get(magic=MAGIC_NUMBER)
                positions = await run_mt5_task(_get_positions)
                
                pos_list = []
                current_tickets = set()
                if positions:
                    for p in positions:
                        current_tickets.add(p.ticket)
                        pos_list.append({
                            "ticket": p.ticket,
                            "symbol": p.symbol,
                            "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                            "volume": p.volume,
                            "price": p.price_open,
                            "profit": p.profit,
                            "sl": getattr(p, 'sl', 0.0),
                            "magic": getattr(p, 'magic', MAGIC_NUMBER),
                            "price_current": getattr(p, 'price_current', p.price_open),
                            "time": getattr(p, 'time', 0)
                        })
                
                closed_tickets = getattr(self, '_known_tickets', set()) - current_tickets
                for ticket in closed_tickets:
                    def _get_deals():
                        return mt5.history_deals_get(position=ticket)
                    deals = await run_mt5_task(_get_deals)
                    if deals:
                        net_pnl = sum([d.profit + d.swap + d.commission for d in deals])
                        await self._log_and_publish(f"CLOSED_SYNC: Position {ticket} closed. Net PNL: ${net_pnl:.2f}", "info")
                        await self.event_bus.publish(OrderEvent(
                            ticket=ticket,
                            symbol="UNKNOWN",
                            direction="CLOSED_SYNC",
                            volume=0.0,
                            price=net_pnl,
                            status="CLOSED_SYNC"
                        ))
                self._known_tickets = current_tickets
                
                def _get_account_info():
                    a_info = mt5.account_info()
                    t_info = mt5.terminal_info()
                    if t_info is None or a_info is None:
                        logger.warning("Terminal disconnected or account info unavailable. Re-initializing MT5...")
                        init_args = {}
                        if self.terminal_path:
                            init_args['path'] = self.terminal_path
                        mt5.initialize(**init_args)
                        a_info = mt5.account_info()
                    return a_info
                acc_info = await run_mt5_task(_get_account_info)
                
                bal = float(getattr(acc_info, 'balance', 0.0)) if acc_info else 0.0
                cred = float(getattr(acc_info, 'credit', 0.0)) if acc_info and isinstance(getattr(acc_info, 'credit', None), (int, float)) else 0.0
                effective_bal = bal + cred
                eq = float(getattr(acc_info, 'equity', 0.0)) if acc_info else 0.0
                fm = getattr(acc_info, 'margin_free', 0.0) if acc_info else 0.0
                ml = getattr(acc_info, 'margin_level', 0.0) if acc_info else 0.0
                login_id = getattr(acc_info, 'login', 0) if acc_info else 0
                acc_name = getattr(acc_info, 'name', "N/A") if acc_info else "N/A"
                acc_server = getattr(acc_info, 'server', getattr(acc_info, 'company', "N/A")) if acc_info else "N/A"
                
                # Phase 19: The Midnight Alignment (Timezone Sync)
                import datetime
                try:
                    import zoneinfo
                    tz = zoneinfo.ZoneInfo(config.PROP_FIRM_RESET_TZ)
                    current_time_tz = datetime.datetime.now(datetime.timezone.utc).astimezone(tz)
                except Exception as e:
                    logger.critical(f"Invalid timezone {config.PROP_FIRM_RESET_TZ}, falling back to UTC. {e}")
                    current_time_tz = datetime.datetime.now(datetime.timezone.utc)
                
                trading_day = current_time_tz.date()
                if current_time_tz.hour < config.PROP_FIRM_RESET_HOUR:
                    trading_day -= datetime.timedelta(days=1)
                
                # FTMO/Prop Firm Drawdown Guardian Logic
                if self._start_equity is None and eq > 0:
                    self._start_equity = max(eq, effective_bal)
                    self._current_day = trading_day
                    
                if self._current_day is not None and self._current_day != trading_day:
                    if eq > 0:
                        self._start_equity = max(eq, effective_bal)
                        self._current_day = trading_day
                        self._panic_halt = False
                        self.risk_manager.reset_daily_state(self._start_equity)
                        
                        from src.core.event_bus import CommandEvent
                        await self.event_bus.publish(CommandEvent(action="DAILY_RESET"))
                        await self._log_and_publish(f"MIDNIGHT ROLLOVER: Prop-Firm Midnight Alignment triggered: Daily Risk Limits Reset at {config.PROP_FIRM_RESET_HOUR:02d}:00 {config.PROP_FIRM_RESET_TZ}")
                        
                if acc_info is not None:
                    await self.risk_manager.check_drawdown_limits(eq, self._start_equity or 0.0)
                
                await self.event_bus.publish(PositionsUpdateEvent(
                    positions=pos_list,
                    balance=bal,
                    equity=eq,
                    free_margin=fm,
                    margin_level=ml,
                    login=login_id,
                    account_name=acc_name,
                    server=acc_server
                ))
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Loop Error in position broadcaster")
                await asyncio.sleep(0.5)

    def _get_filling_mode(self, symbol: str) -> int:
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return mt5.ORDER_FILLING_FOK
        filling = symbol_info.filling_mode
        if filling & 1:
            return mt5.ORDER_FILLING_FOK
        elif filling & 2:
            return mt5.ORDER_FILLING_IOC
        return mt5.ORDER_FILLING_RETURN

    async def handle_error(self, event: ErrorEvent) -> None:
        msg = event.message.upper()
        if event.critical and ("PANIC" in msg or "LOSS EXCEEDED" in msg or "TARGET HIT" in msg):
            self._panic_halt = True
            logger.critical(f"MT5Bridge: CRITICAL HALT RECEIVED ({event.message}). Closing all positions and orders.")
            await self._execute_tactical_action("PANIC_HALT")

    async def process_command(self, event: Any) -> None:
        if event.action == "PANIC_HALT":
            self._panic_halt = True
            logger.critical("MT5Bridge: TELEGRAM PANIC COMMAND RECEIVED. Liquidating all positions and orders.")
            await self._execute_tactical_action("PANIC_HALT")
        elif event.action == "FLAT_BOOK":
            logger.info("MT5Bridge: FLAT_BOOK COMMAND RECEIVED. Liquidating all positions instantly.")
            await self._execute_tactical_action("FLAT_BOOK")

    async def _check_doomsday_shields(self, signal: SignalEvent) -> bool:
        if self._panic_halt:
            await self._log_and_publish("PANIC HALT active. Ignoring signal.")
            return False

        # ALL TRADE LIMITS REMOVED PER 'OPERATION FIRST BLOOD' DIRECTIVES
        return True

    async def process_signal(self, signal: SignalEvent) -> None:
        if signal.direction not in ["BUY", "SELL"]:
            return
            
        is_swarm = getattr(signal, "strategy_id", "") in ["SWARM_TREND", "SWARM_REVERSAL"]
            
        # Phase 20: Hyper-Pyramiding - Removed Global Cooldown and Machine-Gun Lock
        
        if True:

            if not await self._check_doomsday_shields(signal):
                return
                
            rm = self.risk_manager
            
            acc_info = await run_mt5_task(mt5.account_info)
            exec_equity = float(getattr(acc_info, 'equity', 0.0)) if acc_info else 0.0
            free_margin = float(getattr(acc_info, 'margin_free', 0.0)) if acc_info else 0.0
            
            symbol = config.TRADING_SYMBOL
            symbol_info = await run_mt5_task(mt5.symbol_info, symbol)
            
            point = getattr(symbol_info, 'point', 1e-5) if symbol_info else 1e-5
            tick_size = getattr(symbol_info, 'trade_tick_size', point) if symbol_info else point
            tick_value = getattr(symbol_info, 'trade_tick_value', 1.0) if symbol_info else 1.0
            point_value = (point / tick_size) * tick_value if tick_size > 0 else 1.0
            
            volume_step = getattr(symbol_info, 'volume_step', 0.01) if symbol_info else 0.01
            volume_min = getattr(symbol_info, 'volume_min', 0.01) if symbol_info else 0.01
            
            tick_info = await run_mt5_task(mt5.symbol_info_tick, symbol)
            action = mt5.ORDER_TYPE_BUY if signal.direction == "BUY" else mt5.ORDER_TYPE_SELL
            price = tick_info.ask if (action == mt5.ORDER_TYPE_BUY and tick_info) else tick_info.bid if tick_info else 0.0
            
            def _calc_margin():
                res = mt5.order_calc_margin(action, symbol, 1.0, price)
                return res if res is not None else 1000.0
            
            margin_rate = await run_mt5_task(_calc_margin)
                
            risk_percent = getattr(config, 'BASE_RISK_PCT', 0.02)
            
            atr_m15 = getattr(signal, 'atr', 0.0)
            if atr_m15 <= 0:
                atr_m15 = self._latest_m15_atr
            if atr_m15 <= 0:
                atr_m15 = self.param_store.get_fallback_atr(symbol)
            sl_points_fb = atr_m15 * 1.5
            
            volume_to_execute = getattr(signal, 'volume', 0.01)
            
            await self._log_and_publish(f"Equity: {exec_equity:.2f}, Risk: {risk_percent*100:.1f}%, SL: {sl_points_fb:.1f} pts, Executing exact volume: {volume_to_execute}", "info")
                
            def _execute_order():
                symbol = config.TRADING_SYMBOL
                symbol_info = mt5.symbol_info(symbol)
                if not symbol_info:
                    return None
                    
                tick_info = mt5.symbol_info_tick(symbol)
                if not tick_info: return None
                
                spread = round((tick_info.ask - tick_info.bid) / symbol_info.point, 2)
                
                spread_multiplier = 1.0
                    
                server_time = datetime.datetime.fromtimestamp(tick_info.time, datetime.timezone.utc)
                if (server_time.hour == 23 and server_time.minute >= 55) or (server_time.hour == 0 and server_time.minute <= 15):
                    # Ignore rollover limits
                    pass

                action = mt5.ORDER_TYPE_BUY if signal.direction == "BUY" else mt5.ORDER_TYPE_SELL
                
                price = tick_info.ask if action == mt5.ORDER_TYPE_BUY else tick_info.bid
                
                if self._latest_m15_atr > 0:
                    sl_points = round(self._latest_m15_atr * 5.0)
                else:
                    sl_points = self.param_store.get_fallback_atr(symbol) * 5.0
                tp_points = 0.0
                
                acc_info = mt5.account_info()
                volume = volume_to_execute
                
                if spread_multiplier < 1.0:
                    original_vol = volume
                    volume = volume * spread_multiplier
                    step = getattr(symbol_info, 'volume_step', 0.01)
                    min_vol = getattr(symbol_info, 'volume_min', 0.01)
                    if step > 0:
                        volume = round(round(volume / step) * step, 8)
                    volume = max(min_vol, volume)
                    
                # Removed margin-based fallback volume constraint to allow Free-Roll Pyramiding

                sl, tp = rm.calculate_sl_tp(symbol, price, signal.direction, volume, atr=self._latest_m15_atr, sl_points=sl_points, tp_points=tp_points)
                # Purged Defensive Logic: Removed RISK_SHIELD_ERROR check since we use naked orders
                digits = symbol_info.digits
                
                # Dynamic Deviation Control
                atr_points = getattr(signal, "atr", 50.0)
                if atr_points <= 0:
                    atr_points = 50.0
                
                # Calculate Tick Velocity
                ticks = mt5.copy_ticks_from(symbol, tick_info.time, 20, mt5.COPY_TICKS_ALL)
                velocity_points = 0.0
                if ticks is not None and len(ticks) >= 20:
                    velocity_points = abs(ticks[-1]['ask'] - ticks[0]['bid']) / symbol_info.point
                
                # High momentum = wider deviation (e.g. 50% of ATR). Low momentum = tight deviation (10% of ATR).
                if velocity_points > (atr_points * 0.2):
                    dev = int(atr_points * 0.5)
                else:
                    dev = int(atr_points * 0.1)
                
                # Floor and Cap deviation
                dev = max(10, min(200, dev))
                
                # Operation: HFT Aggression - Naked Order Protection (Hard Catastrophic SL)
                hard_sl_dist = atr_points * 2.0 * symbol_info.point
                hard_sl = round(price - hard_sl_dist, digits) if action == mt5.ORDER_TYPE_BUY else round(price + hard_sl_dist, digits)
                
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": str(symbol),
                    "volume": float(volume),
                    "type": int(action),
                    "price": round(float(price), digits),
                    "sl": float(hard_sl),
                    "tp": 0.0,
                    "deviation": int(dev),
                    "magic": int(MAGIC_NUMBER),
                    "comment": f"AUREXIS {getattr(signal, 'strategy_id', 'UNKN')}",
                    "type_time": int(mt5.ORDER_TIME_GTC),
                    "type_filling": self._get_filling_mode(str(symbol)),
                }
                
                return request
                
            req = await run_mt5_task(_execute_order)
            if not isinstance(req, dict):
                return
                
            async def _execute_and_retry(req_payload: dict, signal_event: SignalEvent):
                result = None
                retries_for_price = 0
                max_price_retries = 3
                
                # type_filling is already dynamically resolved in _build_market_request
                while True:
                    if getattr(config, 'DRY_RUN', False):
                        import random
                        class MockResult:
                            def __init__(self, request_dict):
                                self.order = random.randint(1000000, 9999999)
                                self.retcode = mt5.TRADE_RETCODE_DONE
                                self.volume = request_dict.get("volume", 0.0)
                                self.price = request_dict.get("price", 0.0)
                        logger.warning(f"DRY RUN: Bypassing order_send. Mocking success for req: {req_payload}")
                        result = MockResult(req_payload)
                    else:
                        def _timed_send(payload):
                            import time
                            start = time.perf_counter()
                            res = mt5.order_send(payload)
                            end = time.perf_counter()
                            return res, (end - start) * 1000.0

                        result, order_latency_ms = await asyncio.to_thread(_timed_send, req_payload)
                        
                        if getattr(self, 'telemetry_state', None):
                            self.telemetry_state.order_latency_ms = order_latency_ms
                            
                        if order_latency_ms > 50.0:
                            warning_msg = f"LATENCY WARNING: Order execution took {order_latency_ms:.2f}ms. Potential broker-side lag."
                            asyncio.create_task(self.event_bus.publish(ErrorEvent(source="ExecutionBridge", message=warning_msg, critical=False)))
                        
                        if result is None:
                            err = await asyncio.to_thread(mt5.last_error)
                            logger.error(f"RAW EXECUTION EXPOSURE: mt5.order_send returned None. mt5.last_error() = {err}")
                        else:
                            try:
                                raw_dict = result._asdict()
                            except AttributeError:
                                raw_dict = str(result)
                            logger.info(f"RAW EXECUTION EXPOSURE: Raw MT5 response dict: {raw_dict}")
                            logger.info(f"Exact MT5 Response: {result}")
                        
                    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                        if not getattr(config, 'DRY_RUN', False) and result:
                            req_price = float(req_payload.get('price', 0.0))
                            filled_price = float(getattr(result, 'price', req_price))
                            sym = req_payload.get('symbol', '')
                            sym_info = await asyncio.to_thread(mt5.symbol_info, sym)
                            point = getattr(sym_info, 'point', 0.001) if sym_info else 0.001
                            slippage_pts = abs(req_price - filled_price) / point if point > 0 else 0.0
                            lat = locals().get('order_latency_ms', 0.0)
                            asyncio.create_task(self.profiler.log_execution(
                                ticket=getattr(result, 'order', 0),
                                symbol=sym,
                                action=req_payload.get('type', 0),
                                requested_price=req_price,
                                filled_price=filled_price,
                                slippage_pts=slippage_pts,
                                latency_ms=lat
                            ))
                        break
                        
                    if result and result.retcode in [mt5.TRADE_RETCODE_CONNECTION, mt5.TRADE_RETCODE_REQUOTE, mt5.TRADE_RETCODE_PRICE_CHANGED, mt5.TRADE_RETCODE_PRICE_OFF, 10004, 10008, 10009, 10020, 10015, 10016]:
                        if retries_for_price < max_price_retries:
                            retries_for_price += 1
                            logger.warning(f"Order retry {retries_for_price}/{max_price_retries} due to requote/price change (retcode: {result.retcode})")
                            # Operation: Terminal Edge - Aggressive Execution Retry Matrix micro-delay
                            await asyncio.sleep(0.02)
                            fresh_tick = await asyncio.to_thread(mt5.symbol_info_tick, req_payload['symbol'])
                            if fresh_tick:
                                req_payload['price'] = fresh_tick.ask if req_payload['type'] == mt5.ORDER_TYPE_BUY else fresh_tick.bid
                                symbol_info = await asyncio.to_thread(mt5.symbol_info, req_payload['symbol'])
                                if symbol_info:
                                    req_payload['price'] = round(float(req_payload['price']), symbol_info.digits)
                                    # Recalculate Hard SL for new exact price
                                    atr_points = getattr(signal_event, "atr", 50.0)
                                    if atr_points <= 0: atr_points = 50.0
                                    hard_sl_dist = atr_points * 2.0 * symbol_info.point
                                    req_payload['sl'] = round(req_payload['price'] - hard_sl_dist, symbol_info.digits) if req_payload['type'] == mt5.ORDER_TYPE_BUY else round(req_payload['price'] + hard_sl_dist, symbol_info.digits)
                            continue
                        else:
                            logger.error(f"TERMINAL REJECTION: Failed to execute after {max_price_retries} attempts.")
                    
                    if result and result.retcode == 10027:
                        logger.critical("AutoTrading Disabled (10027). Please enable it in MT5.")
                        
                    if result and result.retcode in [mt5.TRADE_RETCODE_INVALID_FILL, mt5.TRADE_RETCODE_INVALID_VOLUME]:
                        logger.error(f"Execution rejected: Invalid Fill/Volume (retcode: {result.retcode}). Symbol likely doesn't support the requested volume or mode.")
                        
                    break
                
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    self._last_order_time = time.time()
                    fill_time = time.time()
                    
                    if self.telemetry_logger:
                        gen_time = getattr(signal_event, "generation_time", getattr(signal_event, "time", fill_time - 0.05))
                        self.telemetry_logger.record_latency(
                            signal_generation_time=gen_time,
                            fill_time=fill_time,
                            ticket=result.order,
                            symbol=config.TRADING_SYMBOL
                        )
                        
                        self.telemetry_logger.record_slippage(
                            requested_price=signal_event.price,
                            fill_price=result.price,
                            ticket=result.order,
                            symbol=config.TRADING_SYMBOL,
                            direction=signal_event.direction
                        )
                    
                    order_event = OrderEvent(
                        ticket=result.order,
                        symbol=config.TRADING_SYMBOL,
                        direction=signal_event.direction,
                        volume=result.volume,
                        price=result.price,
                        status="FILLED",
                        cycle_id=getattr(signal_event, "cycle_id", 0),
                        order_type=getattr(signal_event, "order_type", "PROBE"),
                        requested_price=signal_event.price,
                        conviction=getattr(signal_event, "conviction", 0.0),
                        regime="TRENDING" if getattr(signal_event, "conviction", 0.0) >= 50.0 else "SIDEWAYS",
                        soft_sl=getattr(signal_event, "soft_sl", 0.0),
                        soft_tp=getattr(signal_event, "soft_tp", 0.0)
                    )
                    await self.event_bus.publish(order_event)
                    await self._log_and_publish(f"FILLED: {signal_event.direction} {config.TRADING_SYMBOL} Vol: {result.volume} at {result.price} (Ticket: {result.order})", "info")
                else:
                    err = await asyncio.to_thread(mt5.last_error)
                    if isinstance(err, tuple) and len(err) == 2:
                        err_dict = {"error_code": err[0], "description": err[1]}
                    else:
                        err_dict = {"error": str(err)}
                        
                    retcode = getattr(result, 'retcode', 'Unknown')
                    comment = getattr(result, 'comment', 'None')
                    error_msg = f"FATAL REJECTION TELEMETRY: Order failed after {retries_for_price} price retries. RetCode={retcode}, LastError={err_dict}, Comment={comment}. Request: {req_payload}"
                    logger.error(error_msg)
                    from src.core.event_bus import ErrorEvent
                    await self.event_bus.publish(ErrorEvent(source="MT5Bridge", message=error_msg, critical=True))

            asyncio.create_task(_execute_and_retry(req, signal))
    async def process_order_request(self, event: OrderEvent) -> None:
        if event.status != "REQUEST":
            return
            
        if True:
            if event.direction in ["HARVEST_ALL", "CHOP_50", "PANIC_HALT"]:
                await self._execute_tactical_action(event.direction)
            elif event.direction == "CLOSE":
                await self._close_position(event.ticket, order_type=event.order_type)
            elif event.direction == "MODIFY_SL":
                await self._modify_sl(event.symbol, event.ticket, event.price)

    async def _close_position(self, ticket: int, volume_pct: float = 1.0, order_type: str = "PROBE"):
        if order_type == "CHOP_50":
            volume_pct = 0.5
            
        def _close():
            pos = mt5.positions_get(ticket=ticket)
            if not pos: return None
            pos = pos[0]
            
            # Prevent closing min volume
            if pos.volume <= 0.01 and volume_pct < 1.0:
                logger.info(f"Bridge: Ticket {ticket} has min volume {pos.volume}. Ignoring partial close.")
                return None
                
            tick = mt5.symbol_info_tick(pos.symbol)
            action = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = tick.bid if action == mt5.ORDER_TYPE_SELL else tick.ask
            
            symbol_info = mt5.symbol_info(pos.symbol)
            vol_step = symbol_info.volume_step
            volume = pos.volume * volume_pct
            volume = round(volume / vol_step) * vol_step
            if volume <= 0: return None
            
            digits = symbol_info.digits
            
            atr_points = self._latest_m15_atr if getattr(self, '_latest_m15_atr', 0) > 0 else 50.0
            ticks = mt5.copy_ticks_from(pos.symbol, tick.time, 20, mt5.COPY_TICKS_ALL)
            if ticks is not None and len(ticks) >= 20:
                vel = abs(ticks[-1]['ask'] - ticks[0]['bid']) / symbol_info.point
            else:
                vel = 0.0
            dev = int(atr_points * 0.5) if vel > (atr_points * 0.2) else int(atr_points * 0.1)
            dev = max(10, min(200, dev))
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "volume": float(volume),
                "type": action,
                "price": round(float(price), digits),
                "deviation": dev,
                "magic": MAGIC_NUMBER,
                "comment": "AUREXIS CLOSE",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC if order_type == "IOC" else self._get_filling_mode(pos.symbol),
            }
            if getattr(config, 'DRY_RUN', False):
                import random
                class MockResult:
                    def __init__(self):
                        self.order = request['position']
                        self.retcode = mt5.TRADE_RETCODE_DONE
                        self.price = request['price']
                logger.warning(f"DRY RUN: Bypassing close order. Mocking success for req: {request}")
                return MockResult(), 0.0
            
            import time
            start = time.perf_counter()
            res = mt5.order_send(request)
            end = time.perf_counter()
            return res, (end - start) * 1000.0
            
        result = None
        latency = 0.0
        for attempt in range(3):
            result_tuple = await run_mt5_task(_close)
            if isinstance(result_tuple, tuple):
                result, latency = result_tuple
            else:
                result = result_tuple
            
            if result and result.retcode in [mt5.TRADE_RETCODE_REQUOTE, mt5.TRADE_RETCODE_PRICE_OFF, mt5.TRADE_RETCODE_PRICE_CHANGED, mt5.TRADE_RETCODE_CONNECTION]:
                if attempt < 2:
                    logger.warning(f"Close retry {attempt+1}/3 due to retcode: {result.retcode}")
                    continue
            break
            
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            await self._log_and_publish(f"CLOSED_SYNC: Ticket {ticket} closed at {result.price}", "info")
            if not getattr(config, 'DRY_RUN', False):
                sym_info = await asyncio.to_thread(mt5.symbol_info, pos.symbol)
                point = getattr(sym_info, 'point', 0.001)
                req_price = round(float(price), digits)
                filled_price = float(getattr(result, 'price', req_price))
                slippage_pts = abs(req_price - filled_price) / point if point > 0 else 0.0
                asyncio.create_task(self.profiler.log_execution(
                    ticket=ticket,
                    symbol=pos.symbol,
                    action=mt5.TRADE_ACTION_DEAL,
                    requested_price=req_price,
                    filled_price=filled_price,
                    slippage_pts=slippage_pts,
                    latency_ms=latency
                ))
            await self.event_bus.publish(OrderEvent(ticket, "UNKNOWN", "CLOSE", getattr(result, 'volume', volume), result.price, "FILLED"))
        else:
            err = await asyncio.to_thread(mt5.last_error)
            logger.error(f"Close failed: Error {err}")

    async def _modify_sl(self, symbol: str, ticket: int, new_sl: float):
        def _mod(target_sl):
            pos = mt5.positions_get(ticket=ticket)
            existing_tp = 0.0
            if pos and len(pos) > 0:
                pos = pos[0]
                existing_tp = getattr(pos, 'tp', 0.0)
            else:
                return None
            
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info: return None
            digits = symbol_info.digits
            
            atr_points = getattr(self, '_latest_m15_atr', 50.0)
            if atr_points <= 0: atr_points = 50.0
            dev = int(atr_points * 0.1)
            dev = max(10, min(100, dev))
            
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "symbol": symbol,
                "sl": round(float(target_sl), digits),
                "tp": round(float(existing_tp), digits),
                "deviation": dev,
                "magic": MAGIC_NUMBER
            }
            if getattr(config, 'DRY_RUN', False):
                class MockResult:
                    def __init__(self):
                        self.retcode = mt5.TRADE_RETCODE_DONE
                logger.warning(f"DRY RUN: Bypassing SL modify. Mocking success for req: {request}")
                return MockResult(), 0.0
            
            import time
            start = time.perf_counter()
            res = mt5.order_send(request)
            end = time.perf_counter()
            return res, (end - start) * 1000.0

        result = None
        latency = 0.0
        for attempt in range(5):
            result_tuple = await run_mt5_task(lambda: _mod(new_sl))
            if result_tuple is None:
                break
            if isinstance(result_tuple, tuple):
                result, latency = result_tuple
            else:
                result = result_tuple
                
            if result is None:
                break
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                await self._log_and_publish(f"MODIFIED SL: Ticket {ticket} SL moved to {new_sl}", "info")
                if not getattr(config, 'DRY_RUN', False):
                    asyncio.create_task(self.profiler.log_execution(
                        ticket=ticket,
                        symbol=symbol,
                        action=mt5.TRADE_ACTION_SLTP,
                        requested_price=new_sl,
                        filled_price=new_sl,
                        slippage_pts=0.0,
                        latency_ms=latency
                    ))
                await self.event_bus.publish(OrderEvent(ticket, "UNKNOWN", "MODIFY_SL", 0.0, new_sl, "FILLED"))
                break
            else:
                logger.warning(f"Modify SL retry {attempt+1}/5 failed. Code: {result.retcode}")
                # Requotes or invalid stops due to fast market
                if result.retcode in [mt5.TRADE_RETCODE_REQUOTE, mt5.TRADE_RETCODE_PRICE_OFF, mt5.TRADE_RETCODE_PRICE_CHANGED, mt5.TRADE_RETCODE_CONNECTION, 10004, 10006, mt5.TRADE_RETCODE_INVALID_STOPS]:
                    continue
                else:
                    break
                    
        if result and result.retcode != mt5.TRADE_RETCODE_DONE:
            err = mt5.last_error()
            logger.error(f"Modify SL failed after retries: Error {err}")

    async def _execute_tactical_action(self, action_type: str):
        def _get_positions():
            return mt5.positions_get()
            
        positions = await run_mt5_task(_get_positions)
        if not positions:
            return
            
        for pos in positions:
            magic_val = getattr(pos, 'magic', config.MAGIC_NUMBER)
            if str(type(magic_val)).find("Mock") != -1:
                magic_val = config.MAGIC_NUMBER
            if magic_val != config.MAGIC_NUMBER:
                continue
            if action_type == "HARVEST_ALL" and pos.profit > 0:
                await self._close_position(pos.ticket, 1.0)
            elif action_type == "CHOP_50":
                if pos.volume >= 0.02:
                    await self._close_position(pos.ticket, 0.5)
                else:
                    logger.warning(f"CHOP_50 bypassed for {pos.ticket}: volume {pos.volume} < 0.02 (MT5 limit). Relying on SL trailing.")
            elif action_type in ["PANIC_HALT", "FLAT_BOOK"]:
                await self._close_position(pos.ticket, 1.0)
                
        if action_type in ["PANIC_HALT", "FLAT_BOOK"]:
            def _get_orders():
                return mt5.orders_get()
            orders = await run_mt5_task(_get_orders)
            if orders:
                for ord in orders:
                    if isinstance(getattr(ord, 'magic', None), int) and ord.magic != MAGIC_NUMBER:
                        continue
                    def _cancel(o=ord):
                        req = {"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket}
                        if getattr(config, 'DRY_RUN', False):
                            logger.warning(f"DRY RUN: Bypassing order cancel. Mocking success for req: {req}")
                            return
                        mt5.order_send(req)
                    await run_mt5_task(_cancel)

    async def execute_raw_payload(self, req: dict):
        logger.warning(f"EXECUTING RAW PAYLOAD: {req}")
        result = await run_mt5_task(mt5.order_send, req)
        if result is None:
            err = mt5.last_error()
            print(f"RAW EXECUTION EXPOSURE: mt5.order_send returned None. mt5.last_error() = {err}")
            logger.error(f"RAW EXECUTION EXPOSURE: mt5.order_send returned None. mt5.last_error() = {err}")
        else:
            try:
                raw_dict = result._asdict()
            except AttributeError:
                raw_dict = str(result)
            print(f"RAW EXECUTION EXPOSURE: Raw MT5 response dict: {raw_dict}")
            logger.info(f"RAW EXECUTION EXPOSURE: Raw MT5 response dict: {raw_dict}")
            logger.info(f"Exact MT5 Response: {result}")
