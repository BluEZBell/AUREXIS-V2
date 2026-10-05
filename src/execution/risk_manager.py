from typing import Any, Dict, List, Optional, Tuple, Union, Callable
import os
import json
import asyncio
import time
import datetime
import MetaTrader5 as mt5
from src.core.config import setup_logger, PROFILE_MODE, run_mt5_task
from src.core.event_bus import EventBus, ErrorEvent
import src.core.config as config

logger = setup_logger("risk_manager")


HWM_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "aurexis_hwm.json")
LOCK_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "DOOMSDAY.lock")

class RiskManager:
    def _get_live_balance(self) -> float:
        import MetaTrader5 as mt5
        acc = mt5.account_info()
        if acc:
            try:
                bal = float(getattr(acc, 'balance', 0.0))
                if bal > 0.0:
                    return bal
            except (TypeError, ValueError):
                pass
        raise RuntimeError("Failed to fetch a valid live balance (> 0.0) from MT5.")

    def _get_live_equity(self) -> float:
        import MetaTrader5 as mt5
        acc = mt5.account_info()
        if acc:
            try:
                eq = float(getattr(acc, 'equity', 0.0))
                if eq > 0.0:
                    return eq
            except (TypeError, ValueError):
                pass
        return self._get_live_balance()

    def __init__(self, event_bus: EventBus, live_balance: float, telemetry_state=None):
        self.event_bus = event_bus
        self.telemetry_state = telemetry_state
        self.highest_equity: float = live_balance
        self.consecutive_losses: int = 0
        self.consecutive_probe_failures = 0
        self.halted = False
        
        self.initial_balance = live_balance
        self.session_start_equity = self._get_live_equity()
        self.target_multiplier = 2.0
        
        # Phase 21: High-Water Mark Tracker
        self._hwm = self.initial_balance
        self._doomsday_locked = False
        
        self._vault_secured = False
        self._vault_floor = 0.0

        self.session_start_equity = live_balance
        self.target_multiplier = 2.0

        self._load_hwm_sync(live_balance)

    def _load_hwm_sync(self, live_balance: float = None):
        if live_balance is None:
            live_balance = self.initial_balance

        loaded_hwm = None
        if os.path.exists(HWM_FILE):
            try:
                with open(HWM_FILE, 'r') as f:
                    data = json.load(f)
                    loaded_hwm = data.get("hwm", None)
                    self._vault_secured = data.get("vault_secured", False)
                    self._vault_floor = data.get("vault_floor", 0.0)
            except Exception as e:
                logger.error(f"Failed to load HWM: {e}")
        
        needs_sanitization = False
        
        if loaded_hwm is not None:
            if live_balance > 0:
                variance = abs(loaded_hwm - live_balance) / live_balance
                if variance > 0.5:
                    needs_sanitization = True
                    
        if live_balance > 0 and self.initial_balance == 0.0:
            needs_sanitization = True

        if needs_sanitization:
            logger.warning(f"Corrupted State Detected (Stored HWM: {loaded_hwm}, Live: {live_balance}). Executing Forced State Sanitization.")
            self.initial_balance = live_balance
            self._hwm = live_balance
            self.highest_equity = live_balance
            self._vault_secured = False
            self._vault_floor = 0.0
            
            try:
                with open(HWM_FILE, 'w') as f:
                    json.dump({
                        "hwm": self._hwm,
                        "vault_secured": self._vault_secured,
                        "vault_floor": self._vault_floor
                    }, f)
            except Exception as e:
                logger.error(f"Failed to wipe corrupted HWM state: {e}")
        elif loaded_hwm is not None:
            self._hwm = loaded_hwm
        
        logger.info(f"RiskManager initialized. Current HWM: {self._hwm:.2f}. Vault Secured: {self._vault_secured}, Floor: {self._vault_floor:.2f}. Initial Balance: {self.initial_balance:.2f}. (Type: {config.DRAWDOWN_TYPE}).")

    async def _save_hwm(self):
        def _write():
            with open(HWM_FILE, 'w') as f:
                json.dump({
                    "hwm": self._hwm,
                    "vault_secured": getattr(self, '_vault_secured', False),
                    "vault_floor": getattr(self, '_vault_floor', 0.0)
                }, f)
        await asyncio.to_thread(_write)
        
    async def _trigger_doomsday(self, msg: str):
        if self._doomsday_locked:
            return
        self._doomsday_locked = True
        
        logger.critical(f"DOOMSDAY ALERT (Trading will NOT be halted due to constraints): {msg}")
        
        from src.core.event_bus import RiskAlertEvent
        await self.event_bus.publish(RiskAlertEvent(level="CRITICAL", message=msg))

    def record_trade_result(self, profit: float):
        if profit < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    def release_quota(self, ticket: int):
        if getattr(self, '_locked_risk_amount', None) is None:
            self._locked_risk_amount = 0.0
            
        if not hasattr(self, 'protected_tickets'):
            self.protected_tickets = set()
            
        if ticket not in self.protected_tickets:
            self.protected_tickets.add(ticket)
            
            # Explicitly adjust internal state downward
            if self._locked_risk_amount > 0:
                self._locked_risk_amount *= 0.5 # or manage dynamically
                
            logger.info(f"Risk Vault Recycled: Mathematical risk for ticket {ticket} instantly added back to the available daily risk pool. Free-Roll Pyramiding unlocked.")

    def reset_daily_state(self, current_equity: float):
        self.initial_balance = self._get_live_balance()
        self._hwm = self.initial_balance
        self._doomsday_locked = False
        self._load_hwm_sync()

        try:
            self.highest_equity = float(current_equity)
        except (ValueError, TypeError):
            self.highest_equity = 0.0
        self.consecutive_losses = 0
        self.consecutive_probe_failures = 0
        logger.info(f"Prop-Firm Midnight Alignment triggered: Daily Risk Limits Reset at {config.PROP_FIRM_RESET_HOUR:02d}:00 {config.PROP_FIRM_RESET_TZ}. New base equity: {self.highest_equity}")

    @property
    def is_hyper_conservative(self) -> bool:
        return self.consecutive_losses >= 2

    async def fetch_dynamic_costs(self, symbol: str) -> dict:
        '''
        Async method to fetch exact swap_long and swap_short from mt5.symbol_info.
        '''
        def _fetch():
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return {'swap_long': 0.0, 'swap_short': 0.0, 'spread': 0.0, 'point': 1e-5}
            return {
                'swap_long': getattr(symbol_info, 'swap_long', 0.0),
                'swap_short': getattr(symbol_info, 'swap_short', 0.0),
                'spread': getattr(symbol_info, 'spread', 0.0),
                'point': getattr(symbol_info, 'point', 1e-5)
            }
        return await run_mt5_task(_fetch)

    async def check_drawdown_limits(self, current_equity: float, start_equity: float) -> bool:
        if self.initial_balance <= 0.0:
            logger.warning("RiskManager has 0.00 baseline balance. Boot sequence failed to anchor.")
            return True

        try:
            current_equity = float(current_equity)
            start_equity = float(start_equity)
        except (TypeError, ValueError):
            return True
            
        self.live_equity = current_equity

        if start_equity <= 0:
            return True

        # TASK 1: THE 100% PROFIT SWEEP
        if self.session_start_equity > 0 and current_equity >= (self.session_start_equity * self.target_multiplier):
            logger.info(f"MILESTONE_ACHIEVED: Equity hit target ! Executing FLAT BOOK and resetting session baseline.")
            from src.core.event_bus import OrderEvent, MilestoneEvent, CommandEvent
            asyncio.create_task(self.event_bus.publish(OrderEvent(
                ticket=0, 
                symbol="ALL", 
                direction="HARVEST_ALL", 
                volume=0.0, 
                price=0.0, 
                status="REQUEST"
            )))
            asyncio.create_task(self.event_bus.publish(MilestoneEvent(milestone_name="MILESTONE_ACHIEVED", message="Milestone achieved! Commencing instant Flat Book.")))
            asyncio.create_task(self.event_bus.publish(CommandEvent(action="FLAT_BOOK", payload=None)))
            
            # TASK 3: VAULT RESET & ANCHORING
            # Reset session_start_equity and initial_balance to the newly achieved peak equity
            self.session_start_equity = current_equity
            self.initial_balance = current_equity
            self._hwm = current_equity
            
            # Update the _vault_floor to calculate from the NEW anchored equity
            self._vault_secured = False # Un-secure the vault so the shield applies to the new floor
            self._vault_floor = current_equity * 0.10
            
            asyncio.create_task(self._save_hwm())
            
            if getattr(self, 'telemetry_state', None):
                self.telemetry_state.session_start_equity = self.session_start_equity
                self.telemetry_state.next_milestone_target = self.session_start_equity * self.target_multiplier

        if current_equity > self._hwm:
            self._hwm = current_equity
            asyncio.create_task(self._save_hwm())
            
        import src.core.config as config
        if getattr(config, 'DRAWDOWN_TYPE', '') == "EQUITY_TRAILING":
            ref_balance = self._hwm
        else:
            ref_balance = self.initial_balance
            
        # LINEAR INSTITUTIONAL DRAWDOWN MODEL
        vault_floor = ref_balance * 0.10
        # Ensure our new anchored floor is respected
        vault_floor = max(vault_floor, getattr(self, '_vault_floor', 0.0))
        
        if current_equity <= vault_floor:
            # Enforce hard absolute vault_floor
            msg = f"Hard Vault Floor Reached ({vault_floor:.2f}). Halting to protect capital."
            await self._trigger_doomsday(msg)
            return False

        if current_equity > self.highest_equity:
            try:
                self.highest_equity = float(current_equity)
            except (ValueError, TypeError):
                pass
                
        return True

    def calculate_spread_penalty(self, current_spread: float, baseline_spread: float = 35.0, max_hard_limit: float = 100.0) -> float:
        if current_spread <= baseline_spread:
            return 1.0
        elif baseline_spread < current_spread <= max_hard_limit:
            return baseline_spread / current_spread
        else:
            return 0.0

    def calculate_dynamic_lot(self, equity: float, risk_percent: float, sl_points: float, point_value: float, volume_step: float, volume_min: float, free_margin: float, margin_rate: float, atr: float = None) -> float:
        import math
        import MetaTrader5 as mt5
        
        if atr and atr > 0:
            sl_points = atr * 1.5
        elif sl_points <= 0:
            sl_points = 30.0
            
        if sl_points <= 0 or point_value <= 0:
            return float(volume_min)
            
        unrealized_profit = 0.0
        has_risk_free_tickets = False
        if hasattr(self, 'protected_tickets') and len(self.protected_tickets) > 0:
            positions = mt5.positions_get()
            if positions:
                for p in positions:
                    if p.ticket in self.protected_tickets:
                        unrealized_profit += getattr(p, 'profit', 0.0)
                        has_risk_free_tickets = True
                        
        effective_equity = equity + max(0.0, unrealized_profit)
        risk_amount = effective_equity * risk_percent
        
        ASYMMETRIC_KELLY_MULTIPLIER = 1.25
        if has_risk_free_tickets:
            risk_amount *= ASYMMETRIC_KELLY_MULTIPLIER
            logger.info(f"ASYMMETRIC SCALING: Risk-free tickets detected, applied {ASYMMETRIC_KELLY_MULTIPLIER}x multiplier.")
            
        raw_lot = risk_amount / (sl_points * point_value)
        
        if volume_step > 0:
            lot = math.floor(raw_lot / volume_step) * volume_step
        else:
            lot = raw_lot
            
        lot = round(lot, 8)
        
        import src.core.config as config
        volume_max = getattr(config, 'VOLUME_MAX', 100.0)
        if lot < volume_min:
            return volume_min
        if lot > volume_max:
            lot = volume_max
            
        while lot >= volume_min:
            req_margin = lot * margin_rate
            if req_margin <= free_margin:
                break
            lot -= volume_step
            lot = round(lot, 8)
            
        if lot < volume_min:
            return volume_min
            
        return float(lot)

    def calculate_true_breakeven(self, symbol_info, entry_price: float, direction: str) -> float:
        if not symbol_info:
            return entry_price
        
        swap = symbol_info.swap_long if direction == "BUY" else symbol_info.swap_short
        now = datetime.datetime.now()
        if now.weekday() == 2: # Wednesday triple swap
            swap *= 3
            
        point = symbol_info.point
        swap_points = abs(swap)
        spread_points = symbol_info.spread
        
        # Volatility-pegged or spread-pegged commission approx
        commission_points = spread_points * 1.5 
        friction_points = swap_points + spread_points + commission_points
        friction = friction_points * point
        
        if direction == "BUY":
            return entry_price + friction
        else:
            return entry_price - friction

    async def calculate_lot_size(self, equity: float, atr: float = None, sl_points: float = None, conviction: float = 1.0, oracle_probability: float = None, regime: str = "UNKNOWN", mtf_volume_confirmed: bool = False, is_hyper_scale: bool = False) -> float:
        try:
            symbol = getattr(config, 'TRADING_SYMBOL', 'XAUUSD')
            symbol_info = await run_mt5_task(lambda: mt5.symbol_info(symbol))
            if not symbol_info:
                return 0.0

            # Disable Linear Drawdown Scaling to allow max aggression for 100% daily target
            base_risk_pct = 0.40
            risk_percent = base_risk_pct

            if getattr(self, 'telemetry_state', None):
                self.telemetry_state.session_start_equity = self.session_start_equity
                self.telemetry_state.next_milestone_target = self.session_start_equity * self.target_multiplier
                self.telemetry_state.live_risk_pct = risk_percent * 100.0

            strict_sl_points = (atr * 1.5) if atr and atr > 0 else 30.0
            # P7: Structural Minimum Stop Floor
            MIN_STRUCTURAL_SL = getattr(config, 'MIN_STRUCTURAL_SL_POINTS', 200.0)
            if strict_sl_points < MIN_STRUCTURAL_SL:
                strict_sl_points = MIN_STRUCTURAL_SL

            tick_size = getattr(symbol_info, 'trade_tick_size', 1e-5)
            tick_value = getattr(symbol_info, 'trade_tick_value', 1.0)
            point = getattr(symbol_info, 'point', 1e-5)

            point_value = (point / tick_size) * tick_value if tick_size > 0 else 1.0

            # True Free-Roll Pyramiding Risk Vault
            open_positions = await run_mt5_task(lambda: mt5.positions_get(symbol=symbol))
            pending_orders = await run_mt5_task(lambda: mt5.orders_get(symbol=symbol))
            
            exposed_risk_money = 0.0
            unrealized_profit_rf = 0.0
            has_risk_free_tickets = False
            

            
            if open_positions:
                for p in open_positions:
                    if hasattr(self, 'protected_tickets') and p.ticket in self.protected_tickets:
                        unrealized_profit_rf += getattr(p, 'profit', 0.0)
                        has_risk_free_tickets = True
                        continue
                    
                    sl = getattr(p, 'sl', 0.0)
                    if sl > 0.0:
                        is_buy = getattr(p, 'type', 0) == 0
                        if is_buy and sl >= p.price_open:
                            risk_points = 0.0
                        elif not is_buy and sl <= p.price_open:
                            risk_points = 0.0
                        else:
                            risk_points = abs(p.price_open - sl) / point
                    else:
                        risk_points = strict_sl_points
                    
                    exposed_risk_money += (risk_points * point_value * p.volume)

            # TASK 1 & 2: Calculate allowable volume based on (Core Equity + Unrealized Profit) * base_risk
            effective_equity = equity + max(0.0, unrealized_profit_rf)
            
            max_vault_risk_money = effective_equity * risk_percent
            available_risk_money = max(0.0, max_vault_risk_money - exposed_risk_money)
            
            if getattr(self, '_locked_risk_amount', 0.0) > 0:
                available_risk_money = max(0.0, available_risk_money - self._locked_risk_amount)
            
            if available_risk_money <= 0.01:
                if has_risk_free_tickets:
                    logger.info("Risk Vault Exhausted, but Risk-Free Free-Roll is ACTIVE. Forcing minimum volume.")
                    volume_min_req = getattr(symbol_info, 'volume_min', 0.01)
                    available_risk_money = (strict_sl_points * point_value * volume_min_req) * 1.5
                else:
                    logger.warning(f"Risk Vault Exhausted: max_vault={max_vault_risk_money:.2f}, exposed={exposed_risk_money:.2f}. Cannot safely add more risk.")
                    return 0.0
                
            conviction_multiplier = min(1.0, conviction / 85.0) if conviction > 0 else 0.0
            allocated_risk_money = available_risk_money * conviction_multiplier
            
            # TASK 2: Asymmetric Kelly Multiplier for Hyper-Scaling
            ASYMMETRIC_KELLY_MULTIPLIER = 2.0
            if has_risk_free_tickets:
                allocated_risk_money *= ASYMMETRIC_KELLY_MULTIPLIER
                logger.info(f"ASYMMETRIC SCALING: Risk-free tickets detected, applied {ASYMMETRIC_KELLY_MULTIPLIER}x multiplier.")

            if is_hyper_scale:
                allocated_risk_money *= 2.0
                logger.info("HYPER-SCALE: Applied 2.0x asymmetric multiplier to base risk allocation.")
            
            raw_lot = allocated_risk_money / (strict_sl_points * point_value) if (strict_sl_points * point_value) > 0 else 0.0

            volume_step = getattr(symbol_info, 'volume_step', 0.01)
            volume_min = getattr(symbol_info, 'volume_min', 0.01)
            volume_max = getattr(symbol_info, 'volume_max', 100.0)

            if volume_step > 0:
                import math
                lot = math.floor(raw_lot / volume_step) * volume_step
            else:
                lot = raw_lot

            lot = round(lot, 8)
            
            # P7: Patience Gate
            # USER OVERRIDE: "No need to protect a demo account. Let it trade fully."
            # We bypass the strict risk budget rejection and force the minimum lot size (0.01) so the bot can actually trade!
            if allocated_risk_money < (strict_sl_points * point_value * volume_min):
                logger.warning(f"Risk Budget Low, but forcing {volume_min} lot for Demo Aggressive Testing.")
                return volume_min
            
            if lot < volume_min:
                return volume_min

            action = mt5.ORDER_TYPE_BUY
            price = symbol_info.ask
            
            req_margin = await run_mt5_task(lambda: mt5.order_calc_margin(action, symbol, lot, price))

            acc_info = await run_mt5_task(mt5.account_info)
            free_margin = getattr(acc_info, 'margin_free', 0.0) if acc_info else 0.0

            if req_margin is not None and req_margin > 0 and lot > 0:
                margin_per_lot = req_margin / lot
                max_lot_by_margin = free_margin / margin_per_lot
                if lot > max_lot_by_margin:
                    lot = max_lot_by_margin
                    
            if volume_step > 0:
                import math
                lot = math.floor(lot / volume_step) * volume_step
            lot = round(lot, 8)
            
            if raw_lot > 0 and lot < volume_min:
                if req_margin and req_margin > 0:
                    margin_per_lot = req_margin / (lot if lot > 0 else volume_min)
                    if free_margin >= margin_per_lot * volume_min:
                        lot = volume_min
                    else:
                        lot = 0.0
                else:
                    lot = volume_min

            if lot > volume_max:
                lot = volume_max

            if lot < volume_min:
                return volume_min

            logger.info(f"UNRESTRICTED COMPOUNDING: Eq:  | Risk: {risk_percent*100:.2f}% | SL: {strict_sl_points:.1f} pts | Final Vol: {lot}")

            return float(lot)
        except Exception as e:
            logger.error(f"calculate_lot_size math error: {e}. Returning 0.0 volume.")
            return 0.0

    def calculate_sl_tp(self, symbol: str, entry_price: float, direction: str, volume: float, atr: float = None, sl_multiplier: float = 1.5, tp_multiplier: float = 3.0, sl_points: float = None, tp_points: float = None) -> tuple:
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return 0.0, 0.0
            
        point = symbol_info.point
        
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 50)
        structural_sl_points = None
        
        if rates is not None and len(rates) >= 5:
            import numpy as np
            highs = np.array([x['high'] for x in rates])
            lows = np.array([x['low'] for x in rates])
            from src.core.math_engine import calc_recent_swing_high_low
            swing_high, swing_low = calc_recent_swing_high_low(highs, lows)
            
            buffer = (atr * 0.2) * point if atr else (50 * point)
            if direction == "BUY":
                structural_sl_price = swing_low - buffer
                structural_sl_points = (entry_price - structural_sl_price) / point
            else:
                structural_sl_price = swing_high + buffer
                structural_sl_points = (structural_sl_price - entry_price) / point

        if atr is None and sl_points is not None:
            atr = sl_points / sl_multiplier
        elif atr is None:
            atr = 200.0

        if structural_sl_points and structural_sl_points > 0:
            dynamic_sl_points = structural_sl_points
        else:
            dynamic_sl_points = atr * sl_multiplier
            
        import src.core.config as config
        min_sl = getattr(config, 'MIN_STRUCTURAL_SL_POINTS', 200.0)
        if dynamic_sl_points < min_sl:
            dynamic_sl_points = min_sl
            
        dynamic_tp_points = dynamic_sl_points * (tp_multiplier / sl_multiplier) if sl_multiplier > 0 else dynamic_sl_points * 2.0

        acc_info = mt5.account_info()
        equity = getattr(acc_info, 'equity', 0.0) if acc_info else 0.0
        
        if direction == "BUY":
            sl = entry_price - (dynamic_sl_points * point)
            tp = entry_price + (dynamic_tp_points * point)
        else: # SELL
            sl = entry_price + (dynamic_sl_points * point)
            tp = entry_price - (dynamic_tp_points * point)
            
        return sl, tp

