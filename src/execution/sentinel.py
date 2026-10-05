import asyncio
import time
import MetaTrader5 as mt5
from typing import Dict
from src.core.event_bus import EventBus, TickEvent, OrderEvent, StructuralTrendEvent, TargetHitEvent, SentinelKillEvent, WeekendBlackoutEvent
from src.core.config import setup_logger, run_mt5_task, MAGIC_NUMBER; import src.core.config as config
import src.core.config as config
from src.core.event_bus import StrategyStateEvent

logger = setup_logger("tick_sentinel")

class TickSentinel:
    def __init__(self, event_bus: EventBus, risk_manager, campaign_ledger, friction_engine=None):
        self.event_bus = event_bus
        self.risk_manager = risk_manager
        self.campaign_ledger = campaign_ledger
        from src.execution.dynamic_friction import DynamicFrictionEngine
        self.friction_engine = friction_engine or DynamicFrictionEngine(event_bus)
        
        self.mfe_vault: Dict[int, float] = {}
        self.closing_tickets = set()
        self.profit_floors: Dict[int, float] = {}
        self._last_logged_floor: Dict[int, float] = {}
        self._current_multiplier_tier: Dict[int, float] = {}
        self._running = False
        self._latest_m15_trend = None
        self._news_blackout_active = False
        
        self.event_bus.subscribe(TickEvent, self.process_tick)
        self.event_bus.subscribe(StructuralTrendEvent, self._handle_structure)
        self.event_bus.subscribe(StrategyStateEvent, self._handle_strategy_state)
        from src.core.event_bus import NewsBlackoutEvent
        self.event_bus.subscribe(NewsBlackoutEvent, self._handle_news_blackout)
        self.event_bus.subscribe(WeekendBlackoutEvent, self._handle_weekend_blackout)
        logger.info("Tick Sentinel initialized with MFE Vault and Virtual SL.")

    async def _handle_strategy_state(self, event: StrategyStateEvent):
        self._latest_atr_m15 = getattr(event, "atr_m15", 0.0)

    async def _handle_news_blackout(self, event):
        self._news_blackout_active = event.active

    async def _handle_weekend_blackout(self, event):
        if event.active:
            logger.critical("TickSentinel: WEEKEND FLAT-LINE PROTOCOL triggered. Executing ruthless market liquidation of ALL open positions!")
            active_cycles = list(self.campaign_ledger.active_cycles.values())
            for cycle in active_cycles:
                await self._liquidate_cycle(cycle, "WEEKEND_LIQUIDATION")

    async def _handle_structure(self, event: StructuralTrendEvent):
        self._latest_m15_trend = getattr(event, "m15_trend", None)
        self._live_poc = getattr(event, "poc", 0.0)

    async def sweep_cycles(self):
        active_cycles = list(self.campaign_ledger.active_cycles.values())
        
        positions = await run_mt5_task(lambda: mt5.positions_get(symbol=config.TRADING_SYMBOL))
        
        for cycle in active_cycles:
                
            # Find cycle positions
            cycle_positions = []
            if positions:
                for pos in positions:
                    if pos.ticket == cycle.probe_ticket or pos.ticket in getattr(cycle, 'set_tickets', []):
                        cycle_positions.append(pos)
                        
            # Removed Time Decay Kill logic due to critical constraints
            # 3. Structural Kill
            if self._latest_m15_trend:
                if (cycle.direction == "BUY" and self._latest_m15_trend == "BEARISH") or \
                   (cycle.direction == "SELL" and self._latest_m15_trend == "BULLISH"):
                    logger.warning(f"TickSentinel: Structural kill for cycle {cycle.cycle_id}")
                    await self._liquidate_cycle(cycle, "STRUCTURAL_KILL")
                    continue

    async def _liquidate_cycle(self, cycle, reason):
        cycle.state = "IDLE"
        cycle.exit_reason = reason
        await self.campaign_ledger.save_cycle(cycle)
        
        tick_info = await run_mt5_task(lambda: mt5.symbol_info_tick(config.TRADING_SYMBOL))
        close_price_buy = tick_info.bid if tick_info else 0.0
        close_price_sell = tick_info.ask if tick_info else 0.0
        
        price = close_price_buy if cycle.direction == "BUY" else close_price_sell
        
        if cycle.probe_ticket:
            await self.event_bus.publish(OrderEvent(cycle.probe_ticket, config.TRADING_SYMBOL, "CLOSE", 0.0, price, "REQUEST", cycle.cycle_id))
            await self.event_bus.publish(SentinelKillEvent(cycle.probe_ticket, cycle.cycle_id, reason, cycle.cycle_pnl))
        for tkt in getattr(cycle, 'set_tickets', []):
            await self.event_bus.publish(OrderEvent(tkt, config.TRADING_SYMBOL, "CLOSE", 0.0, price, "REQUEST", cycle.cycle_id))
            await self.event_bus.publish(SentinelKillEvent(tkt, cycle.cycle_id, reason, cycle.cycle_pnl))

    async def start(self):
        self._running = True
        logger.info("Tick Sentinel Task Started.")
        while self._running:
            try:
                await self.sweep_cycles()
            except Exception as e:
                logger.error(f"Error in sweep_cycles: {e}")
            await asyncio.sleep(1.0)
            
    def stop(self):
        self._running = False
        logger.info("Tick Sentinel Task Stopped.")

    async def process_tick(self, event: TickEvent):
        if not self._running:
            return
            
        if event.symbol != config.TRADING_SYMBOL:
            return
            
        def _get_positions():
            return mt5.positions_get(symbol=config.TRADING_SYMBOL)
            
        positions = await run_mt5_task(_get_positions)
        if not positions:
            self.mfe_vault.clear()
            self.profit_floors.clear()
            self._last_logged_floor.clear()
            self.closing_tickets.clear()
            return
            
        active_tickets = set()
        
        # Phase 23: Momentum Exhaustion Sentinel
        if not hasattr(self, '_tick_history'):
            self._tick_history = []
            
        self._tick_history.append((time.time(), event.bid, event.ask))
        if len(self._tick_history) > 20:
            self._tick_history.pop(0)
            
        exhaustion_buy = False
        exhaustion_sell = False
        if len(self._tick_history) >= 20:
            hist_time = [x[0] for x in self._tick_history]
            hist_bid = [x[1] for x in self._tick_history]
            hist_ask = [x[2] for x in self._tick_history]
            
            atr = getattr(self, '_latest_atr_m15', 200.0)
            snapback_threshold = atr * 0.10 if atr > 0 else 0.20
            
            # Velocity Calculation (using 5-tick rolling diff)
            velocities_buy = []
            velocities_sell = []
            for i in range(5, 20):
                dt = hist_time[i] - hist_time[i-5]
                if dt > 0:
                    velocities_buy.append((hist_bid[i] - hist_bid[i-5]) / dt)
                    velocities_sell.append((hist_ask[i-5] - hist_ask[i]) / dt)
            
            peak_vel_buy = max(velocities_buy) if velocities_buy else 0
            curr_vel_buy = velocities_buy[-1] if velocities_buy else 0
            
            peak_vel_sell = max(velocities_sell) if velocities_sell else 0
            curr_vel_sell = velocities_sell[-1] if velocities_sell else 0
            
            # Snapback within last 10 seconds
            recent_10s_idx = 0
            for i in range(20):
                if hist_time[-1] - hist_time[i] <= 10.0:
                    recent_10s_idx = i
                    break
            
            max_bid_10s = max(hist_bid[recent_10s_idx:])
            min_ask_10s = min(hist_ask[recent_10s_idx:])
            
            snapback_buy = (max_bid_10s - hist_bid[-1]) > snapback_threshold
            snapback_sell = (hist_ask[-1] - min_ask_10s) > snapback_threshold
            
            if (peak_vel_buy > 0 and curr_vel_buy < peak_vel_buy * 0.5) or snapback_buy:
                exhaustion_buy = True
            if (peak_vel_sell > 0 and curr_vel_sell < peak_vel_sell * 0.5) or snapback_sell:
                exhaustion_sell = True
        
        # We don't forcefully close via Volatility Harvest loops anymore; 
        # exhaustion is handled per ticket in the positions loop below.
        
        # Fetch shared MT5 state outside the loop to optimize Nano Break-Even and Ghost Target performance
        def _fetch_state():
            s = mt5.symbol_info(config.TRADING_SYMBOL)
            a = mt5.account_info()
            return s, a
            
        sym_info, acc_info = await run_mt5_task(_fetch_state)
        if not sym_info:
            return
            
        equity = 100.0
        if acc_info:
            try:
                equity = float(getattr(acc_info, 'equity', 100.0))
            except (ValueError, TypeError):
                pass
        
        ticket_to_regime = {}
        for cycle in self.campaign_ledger.active_cycles.values():
            regime = getattr(cycle, 'regime_at_entry', '')
            if regime:
                if cycle.probe_ticket:
                    ticket_to_regime[cycle.probe_ticket] = regime
                for tkt in getattr(cycle, 'set_tickets', []):
                    ticket_to_regime[tkt] = regime
        
        live_poc = getattr(self, "_live_poc", 0.0)
        
        for pos in positions:
            magic_val = getattr(pos, 'magic', MAGIC_NUMBER)
            if str(type(magic_val)).find("Mock") != -1:
                magic_val = MAGIC_NUMBER
            if magic_val != MAGIC_NUMBER:
                continue
                
            ticket = pos.ticket
            current_profit = pos.profit
            active_tickets.add(ticket)
            
            if ticket in self.closing_tickets:
                continue
                
            current_mfe = self.mfe_vault.get(ticket, 0.0)
            new_mfe = max(current_mfe, current_profit)
            self.mfe_vault[ticket] = new_mfe
            
            if sym_info.trade_tick_size > 0:
                spread_in_ticks = (event.ask - event.bid) / sym_info.trade_tick_size
                spread_cost_usd = spread_in_ticks * sym_info.trade_tick_value * pos.volume
            else:
                spread_cost_usd = 0.0
            
            atr_m15 = getattr(self, '_latest_atr_m15', 0.0)
            
            # Task 1: Nano Break-Even Engine
            import datetime
            swap = sym_info.swap_long if pos.type == mt5.ORDER_TYPE_BUY else sym_info.swap_short
            now = datetime.datetime.now()
            if now.weekday() == 2:
                swap *= 3
            dynamic_offset = self.friction_engine.get_dynamic_offset()
            friction_points = abs(swap) + sym_info.spread + (sym_info.spread * 1.5) + dynamic_offset
            friction_price = friction_points * sym_info.point
            
            if pos.type == mt5.ORDER_TYPE_BUY:
                mfe_price = event.bid - pos.price_open
                be_price = pos.price_open + friction_price
                if mfe_price > (atr_m15 * 0.10) + friction_price:
                    if pos.sl == 0.0 or pos.sl < (be_price - sym_info.point):
                        logger.info(f"Nano Break-Even Engine: Locking BUY Ticket {ticket} at BE+1 ({be_price:.5f})")
                        def _mod_sl_buy():
                            return mt5.order_send({
                                "action": mt5.TRADE_ACTION_SLTP,
                                "position": ticket,
                                "sl": be_price,
                                "tp": pos.tp,
                                "symbol": config.TRADING_SYMBOL
                            })
                        await run_mt5_task(_mod_sl_buy)
            else:
                mfe_price = pos.price_open - event.ask
                be_price = pos.price_open - friction_price
                if mfe_price > (atr_m15 * 0.10) + friction_price:
                    if pos.sl == 0.0 or pos.sl > (be_price + sym_info.point):
                        logger.info(f"Nano Break-Even Engine: Locking SELL Ticket {ticket} at BE+1 ({be_price:.5f})")
                        def _mod_sl_sell():
                            return mt5.order_send({
                                "action": mt5.TRADE_ACTION_SLTP,
                                "position": ticket,
                                "sl": be_price,
                                "tp": pos.tp,
                                "symbol": config.TRADING_SYMBOL
                            })
                        await run_mt5_task(_mod_sl_sell)
            if atr_m15 > 0.0 and sym_info.trade_tick_size > 0:
                atr_allowance_ticks = atr_m15 / sym_info.trade_tick_size
            else:
                atr_allowance_ticks = 200.0  # Fallback to 200.0 points
                
            if new_mfe >= 100.0:
                multiplier = 1.0
            elif new_mfe >= 80.0:
                multiplier = 1.5
            elif new_mfe >= 50.0:
                multiplier = 2.0
            else:
                multiplier = 2.5
                
            # Phase 13: MACRO-NEWS SHIELD ENFORCEMENT
            if self._news_blackout_active:
                multiplier = min(multiplier, 0.25)
                
            current_tier = self._current_multiplier_tier.get(ticket, 2.5)
            if multiplier < current_tier:
                logger.warning(f"MFE Vault: Hyper-Ratcheting engaged for Ticket {ticket}. Choking trade to {multiplier}x ATR.")
                self._current_multiplier_tier[ticket] = multiplier
            elif multiplier > current_tier:
                self._current_multiplier_tier[ticket] = multiplier
                
            dynamic_allowance_usd = atr_allowance_ticks * multiplier * sym_info.trade_tick_value * pos.volume
            new_dynamic_floor = new_mfe - dynamic_allowance_usd
            
            # Base protection layers (Break-even locks)
            activation_tier_1 = spread_cost_usd * 4.0
            activation_tier_0 = spread_cost_usd * 2.0
            
            proposed_floor = None
            if new_mfe >= activation_tier_1:
                proposed_floor = spread_cost_usd * 1.5
            elif new_mfe >= activation_tier_0:
                proposed_floor = spread_cost_usd * 0.5
                
            if proposed_floor is not None:
                new_dynamic_floor = max(new_dynamic_floor, proposed_floor)
                
            current_floor = self.profit_floors.get(ticket)
            
            floor = None
            if current_floor is not None:
                floor = max(current_floor, new_dynamic_floor)
            elif new_dynamic_floor > 0:
                floor = new_dynamic_floor
                
            if floor is not None and (current_floor is None or floor > current_floor):
                self.profit_floors[ticket] = floor
                
                last_logged = self._last_logged_floor.get(ticket, -999.0)
                if floor >= last_logged + 0.10:
                    logger.info(f"MFE Vault: Locking profit floor at ${floor:.2f} for Ticket {ticket}")
                    self._last_logged_floor[ticket] = floor

            close_reason = None
            pos_dir = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
            
            if self._latest_m15_trend:
                if pos_dir == "BUY" and self._latest_m15_trend == "BEARISH":
                    close_reason = "STRUCTURAL_KILL_BEARISH"
                elif pos_dir == "SELL" and self._latest_m15_trend == "BULLISH":
                    close_reason = "STRUCTURAL_KILL_BULLISH"
            
            if floor is not None and current_profit <= floor:
                close_reason = "MFE_HARD_EXIT"
            elif current_profit > 0:
                if pos_dir == "BUY" and exhaustion_buy:
                    close_reason = "MOMENTUM_EXHAUSTION"
                elif pos_dir == "SELL" and exhaustion_sell:
                    close_reason = "MOMENTUM_EXHAUSTION"
                    
            # TASK 2: Ghost Target Engine (Virtual TP)
            if not close_reason and live_poc > 0.0:
                regime = ticket_to_regime.get(ticket)
                if regime in ("RANGE", "EXHAUSTION"):
                    dynamic_offset_price = self.friction_engine.get_dynamic_offset() * sym_info.point
                    if pos_dir == "BUY" and event.bid >= (live_poc + dynamic_offset_price):
                        close_reason = "GHOST_TARGET_HIT"
                    elif pos_dir == "SELL" and event.ask <= (live_poc - dynamic_offset_price):
                        close_reason = "GHOST_TARGET_HIT"
                
            if close_reason:
                logger.warning(f"Tick Sentinel: Executing CLOSE for Ticket {ticket}. Reason: {close_reason}. Profit: ${current_profit:.2f}")
                
                close_price = event.ask if pos_dir == "SELL" else event.bid
                
                close_event = OrderEvent(
                    ticket=ticket,
                    symbol=config.TRADING_SYMBOL,
                    direction="CLOSE",
                    volume=0.0,
                    price=close_price,
                    status="REQUEST",
                    cycle_id=0
                )
                
                self.closing_tickets.add(ticket)
                await self.event_bus.publish(close_event)
                
                await self.event_bus.publish(SentinelKillEvent(
                    ticket=ticket,
                    cycle_id=0,
                    reason=close_reason,
                    pnl=current_profit
                ))
                
        dead_tickets = set(self.mfe_vault.keys()) - active_tickets
        for dt in dead_tickets:
            self.mfe_vault.pop(dt, None)
            self.profit_floors.pop(dt, None)
            self._current_multiplier_tier.pop(dt, None)
            self.closing_tickets.discard(dt)

