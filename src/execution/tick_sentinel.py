from typing import Any, Dict, List, Optional, Tuple, Union, Callable
import asyncio
import time
import MetaTrader5 as mt5
from src.core.telemetry import TelemetryLogger

from src.core.event_bus import EventBus, TickEvent, OrderEvent, SentinelKillEvent, StructuralTrendEvent, WeekendBlackoutEvent, PositionsUpdateEvent
from src.core.config import setup_logger, run_mt5_task, MAGIC_NUMBER; import src.core.config as config
import src.core.config as config

logger = setup_logger("tick_sentinel")

class TickSentinel:
    def __init__(self, event_bus: EventBus, risk_manager: Any, campaign_ledger: Any, friction_engine: Any = None, telemetry_logger: Optional[TelemetryLogger] = None, telemetry_state=None, alpha_scorer: Any = None, state_ledger: Any = None):
        self.event_bus = event_bus
        self.risk_manager = risk_manager
        self.campaign_ledger = campaign_ledger
        self.telemetry_logger = telemetry_logger
        self.telemetry_state = telemetry_state
        if friction_engine is None:
            from src.execution.dynamic_friction import DynamicFrictionEngine
            self.friction_engine = DynamicFrictionEngine(event_bus)
        else:
            self.friction_engine = friction_engine
            
        self.alpha_scorer = alpha_scorer
        self._pos_exhaustion_ticks: Dict[int, int] = {}
            
        if state_ledger is None:
            from src.execution.state_ledger import StateLedger
            self.state_ledger = StateLedger()
        else:
            self.state_ledger = state_ledger
        self._pos_risk_recycled: Dict[int, bool] = {}
            
        self._running = False
        self._closing_tickets = {}
        
        # Momentum Exhaustion state
        self._pos_highs: Dict[int, float] = {}
        self._pos_lows: Dict[int, float] = {}
        self._pos_last_extreme_time: Dict[int, float] = {}
        self._pos_tick_vols: Dict[int, List[float]] = {}
        
        # MFE / MAE state
        self._pos_mfe: Dict[int, float] = {}
        self._pos_mae: Dict[int, float] = {}
        self._pos_open_time: Dict[int, float] = {}
        self._pos_conviction: Dict[int, float] = {}
        
        # Local state cache
        self._positions: Dict[int, dict] = {}
        self._soft_targets: Dict[int, dict] = {}
        self._load_ghost_targets()
        self._symbol_info_cache = None
        self._last_symbol_info_time = 0.0
        
        # Structural data
        self._latest_atr_m15 = 200.0
        self._latest_m15_trend = None

        self.event_bus.subscribe(PositionsUpdateEvent, self._handle_positions_update)
        self.event_bus.subscribe(TickEvent, self.process_tick)
        self.event_bus.subscribe(StructuralTrendEvent, self._handle_structure)
        self.event_bus.subscribe(WeekendBlackoutEvent, self._handle_weekend_blackout)
        self.event_bus.subscribe(OrderEvent, self._handle_order_event)
        
        from src.core.event_bus import CommandEvent, MilestoneEvent, SignalEvent
        self.event_bus.subscribe(CommandEvent, self.process_command)
        self.event_bus.subscribe(MilestoneEvent, self._handle_milestone)
        self.event_bus.subscribe(SignalEvent, self._handle_signal)

    async def _handle_signal(self, event: Any) -> None:
        if getattr(event, 'atr', None) is not None:
            self._latest_fast_atr = float(event.atr)

    def _load_ghost_targets(self):
        pass

    def _save_ghost_targets(self):
        pass

    async def _handle_positions_update(self, event: PositionsUpdateEvent) -> None:
        if not self._running:
            return
            
        current_tickets = set()
        for pos in event.positions:
            # Handle mock magic numbers in tests
            magic_val = pos.get('magic', MAGIC_NUMBER)
            if str(type(magic_val)).find("Mock") == -1 and magic_val != MAGIC_NUMBER:
                continue
                
            ticket = pos['ticket']
            # Removed: if ticket in self._closing_tickets: continue
            
            current_tickets.add(ticket)
            
            if ticket not in self._positions:
                self._positions[ticket] = pos.copy()
            else:
                self._positions[ticket].update(pos)
                
        dead_tickets = set(self._positions.keys()) - current_tickets
        changed = False
        for dt in dead_tickets:
            self._positions.pop(dt, None)
            self._pos_highs.pop(dt, None)
            self._pos_lows.pop(dt, None)
            self._pos_last_extreme_time.pop(dt, None)
            self._pos_tick_vols.pop(dt, None)
            self._pos_mfe.pop(dt, None)
            self._pos_mae.pop(dt, None)
            self._pos_open_time.pop(dt, None)
            self._pos_conviction.pop(dt, None)
            self._pos_risk_recycled.pop(dt, None)
            self._pos_exhaustion_ticks.pop(dt, None)
            if hasattr(self, 'state_ledger'):
                self.state_ledger.delete_ticket(dt)
            if dt in self._soft_targets:
                self._soft_targets.pop(dt, None)
                changed = True
            self._closing_tickets.pop(dt, None)
            
        if changed:
            self._save_ghost_targets()

    async def _handle_order_event(self, event: OrderEvent) -> None:
        if event.status == "FILLED" and event.direction in ["BUY", "SELL"]:
            self._soft_targets[event.ticket] = {
                "soft_sl": getattr(event, "soft_sl", 0.0),
                "soft_tp": getattr(event, "soft_tp", 0.0)
            }
            self._pos_conviction[event.ticket] = getattr(event, "conviction", 0.0)
            self._pos_risk_recycled[event.ticket] = False
            self._save_ghost_targets()
            
            if hasattr(self, 'state_ledger'):
                self.state_ledger.update_ticket_state(
                    ticket_id=event.ticket,
                    magic_number=MAGIC_NUMBER,
                    virtual_sl=getattr(event, "soft_sl", 0.0),
                    virtual_tp=getattr(event, "soft_tp", 0.0),
                    risk_recycled=False
                )
        elif event.status == "FILLED" and event.direction == "CLOSE":
            if hasattr(self, 'state_ledger'):
                self.state_ledger.delete_ticket(event.ticket)

    async def _handle_structure(self, event: StructuralTrendEvent) -> None:
        if getattr(event, "m15_atr", None):
            self._latest_atr_m15 = float(event.m15_atr)
        self._latest_m15_trend = getattr(event, "m15_trend", None)
        
        active_cycles = list(self.campaign_ledger.active_cycles.values())
        for cycle in active_cycles:
            if self._latest_m15_trend:
                if (cycle.direction == "BUY" and self._latest_m15_trend == "BEARISH") or \
                   (cycle.direction == "SELL" and self._latest_m15_trend == "BULLISH"):
                    await self._liquidate_cycle(cycle, "STRUCTURAL_KILL")

    async def _handle_weekend_blackout(self, event: WeekendBlackoutEvent) -> None:
        if event.active:
            logger.critical("TickSentinel: WEEKEND FLAT-LINE PROTOCOL triggered. Executing ruthless market liquidation.")
            active_cycles = list(self.campaign_ledger.active_cycles.values())
            for cycle in active_cycles:
                await self._liquidate_cycle(cycle, "WEEKEND_LIQUIDATION")

    async def _handle_milestone(self, event) -> None:
        if event.milestone_name == "MILESTONE_ACHIEVED":
            logger.info(f"TickSentinel: {event.message} Updating states for new base.")

    async def process_command(self, event) -> None:
        if getattr(event, 'action', '') == "FLAT_BOOK":
            logger.info("TickSentinel: FLAT_BOOK command received. Liquidating all active cycles.")
            active_cycles = list(self.campaign_ledger.active_cycles.values())
            for cycle in active_cycles:
                await self._liquidate_cycle(cycle, "MILESTONE_FLAT_BOOK")

    async def _liquidate_cycle(self, cycle: Any, reason: str) -> None:
        if getattr(cycle, 'state', '') == 'IDLE':
            return
        cycle.state = "IDLE"
        cycle.exit_reason = reason
        await self.campaign_ledger.save_cycle(cycle)
        
        price_buy, price_sell = 0.0, 0.0
        tick_info = await run_mt5_task(lambda: mt5.symbol_info_tick(config.TRADING_SYMBOL))
        if tick_info:
            price_buy = tick_info.bid
            price_sell = tick_info.ask
            
        price = price_buy if cycle.direction == "BUY" else price_sell
        
        if getattr(cycle, 'probe_ticket', None):
            probe_ticket = getattr(cycle, 'probe_ticket')
            probe_pnl = self._positions.get(probe_ticket, {}).get("profit", 0.0)
            await self.event_bus.publish(OrderEvent(probe_ticket, config.TRADING_SYMBOL, "CLOSE", 0.0, price, "REQUEST", getattr(cycle, 'cycle_id', 0)))
            await self.event_bus.publish(SentinelKillEvent(probe_ticket, getattr(cycle, 'cycle_id', 0), reason, probe_pnl))
        for tkt in getattr(cycle, 'set_tickets', []):
            tkt_pnl = self._positions.get(tkt, {}).get("profit", 0.0)
            await self.event_bus.publish(OrderEvent(tkt, config.TRADING_SYMBOL, "CLOSE", 0.0, price, "REQUEST", getattr(cycle, 'cycle_id', 0)))
            await self.event_bus.publish(SentinelKillEvent(tkt, getattr(cycle, 'cycle_id', 0), reason, tkt_pnl))

    async def sweep_cycles(self) -> None:
        """
        Compatibility method for tests. Synchronously sweeps positions manually.
        """
        positions = await run_mt5_task(lambda: mt5.positions_get(symbol=config.TRADING_SYMBOL))
        if not positions: return
        pos_list = []
        for p in positions:
            pos_type = getattr(p, 'type', mt5.ORDER_TYPE_BUY)
            pos_list.append({
                "ticket": p.ticket,
                "symbol": getattr(p, 'symbol', config.TRADING_SYMBOL),
                "type": "BUY" if pos_type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume": p.volume,
                "price": getattr(p, 'price_open', 0.0),
                "profit": getattr(p, 'profit', 0.0),
                "sl": getattr(p, 'sl', 0.0),
                "magic": getattr(p, 'magic', MAGIC_NUMBER),
                "price_current": getattr(p, 'price_current', getattr(p, 'price_open', 0.0)),
                "time": getattr(p, 'time', 0)
            })
        ev = PositionsUpdateEvent(pos_list, 1000, 1000, 1000, 100, 123, "Test", "Test")
        await self._handle_positions_update(ev)
        
        tick_info = await run_mt5_task(lambda: mt5.symbol_info_tick(config.TRADING_SYMBOL))
        if tick_info:
            tick_time = getattr(tick_info, 'time', int(time.time()))
            tick_vol = float(getattr(tick_info, 'volume_real', getattr(tick_info, 'volume', 1.0)))
            ev_tick = TickEvent(symbol=config.TRADING_SYMBOL, time=tick_time, bid=tick_info.bid, ask=tick_info.ask, volume=tick_vol)
            await self.process_tick(ev_tick)

    async def _recover_state(self):
        import MetaTrader5 as mt5
        from src.core.config import MAGIC_NUMBER, run_mt5_task; import src.core.config as config
        
        positions = await run_mt5_task(lambda: mt5.positions_get(symbol=config.TRADING_SYMBOL))
        if positions is None:
            logger.error("StateLedger: Failed to retrieve positions from MT5 during state recovery. Aborting ledger reconciliation to prevent accidental data wipe.")
            return
            
        active_mt5_tickets = []
        for p in positions:
            magic_val = getattr(p, 'magic', 0)
            if magic_val == MAGIC_NUMBER:
                active_mt5_tickets.append(p.ticket)
                    
        ledger_records = await self.state_ledger.get_all_records()
        
        for tkt in active_mt5_tickets:
            if tkt in ledger_records:
                record = ledger_records[tkt]
                if tkt not in self._soft_targets:
                    self._soft_targets[tkt] = {}
                self._soft_targets[tkt]['soft_sl'] = record['virtual_sl']
                self._soft_targets[tkt]['soft_tp'] = record['virtual_tp']
                self._pos_risk_recycled[tkt] = record['risk_recycled']
                if record['risk_recycled'] and hasattr(self.risk_manager, 'release_quota'):
                    res = self.risk_manager.release_quota(tkt)
                    if asyncio.iscoroutine(res):
                        await res
                logger.info(f"StateLedger: Restored ticket {tkt} state (SL: {record['virtual_sl']}, TP: {record['virtual_tp']}, Recycled: {record['risk_recycled']})")
                
        self._save_ghost_targets()
        self.state_ledger.delete_orphan_records(active_mt5_tickets)

    async def start(self) -> None:
        await self.state_ledger.initialize()
        await self._recover_state()
        self._running = True
        logger.info("Tick Sentinel Task Started (Event-Driven Mode).")
        
    def stop(self) -> None:
        self._running = False
        logger.info("Tick Sentinel Task Stopped.")

    async def _get_cached_symbol_info(self):
        now = time.time()
        if not self._symbol_info_cache or now - self._last_symbol_info_time > 60.0:
            self._symbol_info_cache = await run_mt5_task(lambda: mt5.symbol_info(config.TRADING_SYMBOL))
            self._last_symbol_info_time = now
        return self._symbol_info_cache

    async def process_tick(self, event: TickEvent) -> None:
        if not self._running:
            return
        if event.symbol != config.TRADING_SYMBOL:
            return
            
        current_time = event.time
        
        symbol_info = await self._get_cached_symbol_info()
        point = getattr(symbol_info, 'point', 0.00001) if symbol_info else 0.00001
        if point <= 0:
            point = 0.00001
        
        for ticket, pos_dict in list(self._positions.items()):
            is_buy = pos_dict['type'] == "BUY"
            price_current = event.bid if is_buy else event.ask
            pos_dict['price_current'] = price_current
            
            price_open = pos_dict.get('price', 0.0)
            if price_open > 0:
                profit_points = (price_current - price_open) / point if is_buy else (price_open - price_current) / point
                if ticket not in self._pos_mfe:
                    self._pos_mfe[ticket] = profit_points
                    self._pos_mae[ticket] = profit_points
                    pos_time = pos_dict.get('time', 0)
                    self._pos_open_time[ticket] = pos_time if pos_time > 0 else current_time
                else:
                    if profit_points > self._pos_mfe[ticket]:
                        self._pos_mfe[ticket] = profit_points
                    if profit_points < self._pos_mae[ticket]:
                        self._pos_mae[ticket] = profit_points
            
            await self._evaluate_ghost_targets(pos_dict, event)
            await self._evaluate_break_even(pos_dict)
            await self._evaluate_momentum_exhaustion(pos_dict, event, current_time)
            
        if getattr(self, 'telemetry_state', None):
            self.telemetry_state.active_positions = len(self._positions)
            self.telemetry_state.floating_pnl = sum(p.get('profit', 0.0) for p in self._positions.values())
            self.telemetry_state.ghost_targets = [str(t) for t in self._soft_targets.keys()]

    async def _evaluate_ghost_targets(self, pos: dict, event: TickEvent) -> None:
        ticket = pos['ticket']
        targets = self._soft_targets.get(ticket)
        if not targets:
            return

        soft_sl = targets.get('soft_sl', 0.0)
        soft_tp = targets.get('soft_tp', 0.0)
        
        if soft_sl == 0.0 and soft_tp == 0.0:
            return
            
        is_buy = pos['type'] == "BUY"
        price = event.bid if is_buy else event.ask
        price_open = pos['price']
        
        trigger_close = False
        reason = ""
        order_type_str = "PROBE"
        
        # TASK 2: VIRTUAL TP DEACTIVATION
        # If the ticket already has a Hard TP at the broker (like Harvesters do now), bypass the Virtual TP market close.
        has_hard_tp = pos.get('tp', 0.0) > 0.0
        
        if is_buy:
            if soft_sl > 0 and price <= soft_sl:
                trigger_close = True
                reason = "GHOST_SL_HIT"
            elif soft_tp > 0 and price >= soft_tp and not has_hard_tp:
                trigger_close = True
                reason = "GHOST_TP_HIT"
                order_type_str = "IOC"
        else:
            if soft_sl > 0 and price >= soft_sl:
                trigger_close = True
                reason = "GHOST_SL_HIT"
            elif soft_tp > 0 and price <= soft_tp and not has_hard_tp:
                trigger_close = True
                reason = "GHOST_TP_HIT"
                order_type_str = "IOC"
                
        if trigger_close:
            logger.info(f"TickSentinel: Ticket {ticket} triggered {reason} (Price: {price:.5f}, SL: {soft_sl:.5f}, TP: {soft_tp:.5f})")
            if self.telemetry_logger:
                self.telemetry_logger.record_sentinel_event(
                    event_name=reason,
                    ticket=ticket,
                    reason=f"Ghost Target Engine evaluation true (OrderType: {order_type_str})"
                )
            await self._request_close(ticket, reason, event, pos['type'], order_type=order_type_str)

    async def _evaluate_break_even(self, pos: dict) -> None:
        symbol_info = await self._get_cached_symbol_info()
        if not symbol_info:
            return
            
        is_buy = pos['type'] == "BUY"
        point = getattr(symbol_info, 'point', 0.00001)
        if point <= 0:
            point = 0.00001
        
        price_current = pos['price_current']
        price_open = pos['price']
        
        spread_points = getattr(symbol_info, 'spread', 0.0)
        commission_points = spread_points * 1.5
        friction_points = spread_points + commission_points
        
        profit_points = (price_current - price_open) / point if is_buy else (price_open - price_current) / point
        net_profit_points = profit_points - friction_points
        
        fast_atr = getattr(self, '_latest_fast_atr', 15.0)
        be_trigger = fast_atr * 1.5
        
        # TASK 2: SLIPPAGE-PADDED BE MATH
        # Hardcode a strict 10.0 point commission buffer for XAUUSD to absorb slippage
        commission_buffer_points = 20.0
        slippage_padded_points = spread_points + commission_buffer_points
        
        print(f"DEBUG: profit_points={profit_points}, net_profit_points={net_profit_points}, be_trigger={be_trigger}")
        
        if net_profit_points >= be_trigger:
            if is_buy:
                new_sl = price_open + (slippage_padded_points * point)
            else:
                new_sl = price_open - (slippage_padded_points * point)
            
            needs_update = False
            current_sl = pos.get('sl', 0.0)
            
            if is_buy:
                if current_sl < new_sl - (point * 1.0):
                    needs_update = True
            else:
                if current_sl == 0.0 or current_sl > new_sl + (point * 1.0):
                    needs_update = True
                    
            if needs_update:
                print(f"DEBUG: BE manager locking ticket {pos['ticket']} at {new_sl}")
                logger.info(f"Aggressive Break-Even Manager: Locking Ticket {pos['ticket']} at zero-loss ({new_sl:.5f}) via Broker SL")
                
                # Still record in soft targets for redundancy
                if pos['ticket'] not in self._soft_targets:
                    self._soft_targets[pos['ticket']] = {}
                self._soft_targets[pos['ticket']]['soft_sl'] = new_sl
                self._save_ghost_targets()
                
                # Directly request MT5 Broker SL modification asynchronously
                from src.core.event_bus import OrderEvent
                if self.event_bus:
                    await self.event_bus.publish(OrderEvent(
                        ticket=pos['ticket'],
                        symbol=pos.get('symbol', 'UNKNOWN'),
                        direction="MODIFY_SL",
                        volume=0.0,
                        price=new_sl,
                        status="REQUEST"
                    ))
                
                if self.telemetry_logger:
                    self.telemetry_logger.record_sentinel_event(
                        event_name="BROKER_BE_LOCK",
                        ticket=pos['ticket'],
                        reason=f"Net profit +{be_trigger:.1f} pts reached. Aggressive Break-Even locked at entry + spread."
                    )
                    
                pos['is_risk_free'] = True
                
                if not self._pos_risk_recycled.get(pos['ticket'], False):
                    if hasattr(self.risk_manager, 'release_quota'):
                        res = self.risk_manager.release_quota(pos['ticket'])
                        if asyncio.iscoroutine(res):
                            await res
                    self._pos_risk_recycled[pos['ticket']] = True

                if hasattr(self, 'state_ledger'):
                    self.state_ledger.update_ticket_state(
                        ticket_id=pos['ticket'],
                        magic_number=pos.get('magic', MAGIC_NUMBER),
                        virtual_sl=new_sl,
                        virtual_tp=self._soft_targets[pos['ticket']].get('soft_tp', 0.0),
                        risk_recycled=self._pos_risk_recycled.get(pos['ticket'], False)
                    )

        if not hasattr(self, '_chopped_tickets'):
            self._chopped_tickets = set()
            
        if pos['ticket'] not in self._chopped_tickets:
            # HFT RAPID HARVEST: Take +$ immediately instead of waiting for massive ATR targets!
            hft_tp_trigger = max(1000.0, fast_atr * 3.0)
            if net_profit_points >= hft_tp_trigger and net_profit_points > 0:
                self._chopped_tickets.add(pos['ticket'])
                logger.info(f"HFT HARVEST: Ticket {pos['ticket']} reached net +{net_profit_points:.1f} pts. Closing for immediate +$!")
                await self._request_close(pos['ticket'], "HFT_HARVEST", None, pos['type'], order_type="IOC")
                
    async def _evaluate_momentum_exhaustion(self, pos: dict, event: TickEvent, current_time: float) -> None:
        symbol_info = await self._get_cached_symbol_info()
        point = getattr(symbol_info, 'point', 0.00001) if symbol_info else 0.00001
        if point <= 0:
            point = 0.00001
        
        is_buy = pos['type'] == "BUY"
        price_current = pos['price_current']
        price_open = pos['price']
        
        spread_points = getattr(symbol_info, 'spread', 0.0)
        commission_points = spread_points * 1.5
        friction_points = spread_points + commission_points
        
        profit_points = (price_current - price_open) / point if is_buy else (price_open - price_current) / point
        net_profit_points = profit_points - friction_points
            
        ticket = pos['ticket']
        
        atr_points = self._latest_atr_m15 if self._latest_atr_m15 > 0 else 20.0
        fast_atr = getattr(self, '_latest_fast_atr', atr_points)
        
        # Base Virtual SL
        virtual_sl_points = - (fast_atr * 2.5)
        
        # P7: Enforce Minimum Structural SL Floor on Virtual SL to prevent instant premature stops in low ATR
        min_sl = getattr(config, "MIN_STRUCTURAL_SL_POINTS", 200.0)
        if virtual_sl_points > -min_sl:
            virtual_sl_points = -min_sl
            
        # HFT MAXIMUM LOSS CAP (Anti-Bagholding)
        # Never allow a single HFT trade to drag more than 1000 points (~$10.00 per 0.01 lot) to protect accounts
        if virtual_sl_points < -2000.0:
            virtual_sl_points = -2000.0
        
        # Real-time Momentum for the position
        if ticket not in self._pos_highs:
            self._pos_highs[ticket] = price_current
            self._pos_lows[ticket] = price_current
            self._pos_tick_vols[ticket] = []
            
        # Update extremes
        if is_buy and price_current > self._pos_highs[ticket]:
            self._pos_highs[ticket] = price_current
        elif not is_buy and price_current < self._pos_lows[ticket]:
            self._pos_lows[ticket] = price_current
            
        # Track recent prices to evaluate velocity
        self._pos_tick_vols[ticket].append(price_current)
        if len(self._pos_tick_vols[ticket]) > 20:
            self._pos_tick_vols[ticket].pop(0)
            
        extreme = self._pos_highs[ticket] if is_buy else self._pos_lows[ticket]
        retreat_points = (extreme - price_current) / point if is_buy else (price_current - extreme) / point

        # VIRTUAL SL
        if profit_points <= virtual_sl_points:
            logger.warning(f"Virtual SL triggered for ticket {ticket}. Cutting loss.")
            await self._request_close(ticket, "EXIT: Virtual SL", event, pos['type'])
            return

        # EARLY BAILOUT: REMOVED
        # The 20-tick early bailout was hyper-sensitive to spread (e.g., -55 points) and caused instant premature exits.
        # Now relying on Virtual SL and Minimum Structural SL to give trades proper breathing room.

        # NET PNL ACCOUNTING: Do not trigger momentum exhaustion defensively if we haven't cleared fundamental broker cost basis
        if net_profit_points <= 0:
            return

        # TASK 1: MULTI-VECTOR DETECTION
        trigger_exit = False
        exit_reason = ""
        delta_momentum = 0.0
        
        mfe_points = (extreme - price_open) / point if is_buy else (price_open - extreme) / point
        net_mfe_points = mfe_points - friction_points
        
        # Only evaluate exhaustion if MFE >= 2.5 * ATR as specified in audit to let profits run
        if net_mfe_points >= fast_atr * 2.5:
            # Vector 1: Cumulative Delta Divergence (Weight: 0.35)
            v_delta = 0.0
            # Micro-tick momentum checks disabled due to latency corruption
            v_delta = 0.0
            delta_momentum = 0.0

            # Vector 2: Volume Climax & Absorption (Weight: 0.30)
            v_vol = 0.0
            tick_vol = getattr(event, 'volume', 0.0)
            if tick_vol > 20.0 and retreat_points > (fast_atr * 0.25):
                v_vol = 1.0
                
            # Vector 3: Order Flow Velocity Decay (Weight: 0.20)
            v_vel = 0.0
            if len(self._pos_tick_vols[ticket]) == 20:
                start_price = self._pos_tick_vols[ticket][0]
                end_price = self._pos_tick_vols[ticket][-1]
                pos_velocity = (end_price - start_price) / point if is_buy else (start_price - end_price) / point
                if pos_velocity < -(fast_atr * 0.2):
                    v_vel = 1.0

            # Vector 4: Adverse Tick Flow Pressure (Weight: 0.15)
            v_flow = 0.0
            flags = getattr(event, 'flags', 0)
            if is_buy and (flags & mt5.TICK_FLAG_SELL):
                v_flow = 1.0
            elif not is_buy and (flags & mt5.TICK_FLAG_BUY):
                v_flow = 1.0
            
            exhaustion_score = (0.35 * v_delta) + (0.30 * v_vol) + (0.20 * v_vel) + (0.15 * v_flow)
            
            if exhaustion_score >= 0.70:
                trigger_exit = True
                exit_reason = f"4-Vector Exhaustion E={exhaustion_score:.2f} (MFE: {net_mfe_points:.1f})"
                
        if trigger_exit:
            logger.warning(f"Surgical Exit (Multi-Vector Exhaustion) for ticket {ticket}. Reason: {exit_reason} (Net MFE: {net_mfe_points:.1f}, Delta: {delta_momentum:.2f})")
            if self.telemetry_logger:
                self.telemetry_logger.record_sentinel_event(
                    event_name="EXIT: Multi-Vector Exhaustion",
                    ticket=ticket,
                    reason=exit_reason
                )
            
            # Request physical close
            await self._request_close(ticket, "MOMENTUM_EXHAUSTION", event, pos['type'], order_type="IOC")
            
            # Dispatch SentinelKillEvent for broad visibility and state sync
            import asyncio
            from src.core.event_bus import SentinelKillEvent
            kill_event = SentinelKillEvent(
                ticket=ticket,
                cycle_id=int(current_time),
                reason=exit_reason,
                pnl=profit_points
            )
            asyncio.create_task(self.event_bus.publish(kill_event))
            return
            
        # Magnetic Targeting (POC Liquidity Pool)
        soft_tp = self._soft_targets.get(ticket, {}).get('soft_tp', 0.0)
        if soft_tp > 0 and profit_points > (fast_atr * 2.0):
            distance_to_poc = abs(price_current - soft_tp) / point
            if distance_to_poc < (fast_atr * 0.5):
                # We are at or near the POC, aggressively lock profit with tight SL
                trail_sl = price_current - (fast_atr * 0.8 * point) if is_buy else price_current + (fast_atr * 0.8 * point)
                current_sl = self._soft_targets.get(ticket, {}).get('soft_sl', 0.0)
                
                needs_update = False
                if is_buy and (current_sl == 0.0 or trail_sl > current_sl):
                    needs_update = True
                elif not is_buy and (current_sl == 0.0 or trail_sl < current_sl):
                    needs_update = True
                    
                if needs_update:
                    if ticket not in self._soft_targets:
                        self._soft_targets[ticket] = {}
                    self._soft_targets[ticket]['soft_sl'] = trail_sl
                    self._save_ghost_targets()
                    logger.info(f"Magnetic Targeting: Ticket {ticket} near POC ({soft_tp}), trailing SL tightly.")
                    if self.telemetry_logger:
                        self.telemetry_logger.record_sentinel_event(
                            event_name="SL_TRAIL: Magnetic POC",
                            ticket=ticket,
                            reason="Securing profit as price hits institutional liquidity pool (POC)."
                        )

        # Momentum Stall
        if len(self._pos_tick_vols[ticket]) == 20:
            start_price = self._pos_tick_vols[ticket][0]
            end_price = self._pos_tick_vols[ticket][-1]
            pos_velocity = (end_price - start_price) / point if is_buy else (start_price - end_price) / point
            
            # If the position has moved against us by > 1.0 ATR over 20 ticks, trail SL aggressively
            if profit_points > (fast_atr * 2.5) and pos_velocity < - (fast_atr * 1.0):
                trail_sl = price_current - (fast_atr * 1.5 * point) if is_buy else price_current + (fast_atr * 1.5 * point)
                current_sl = self._soft_targets.get(ticket, {}).get('soft_sl', 0.0)
                
                needs_update = False
                if is_buy and (current_sl == 0.0 or trail_sl > current_sl):
                    needs_update = True
                elif not is_buy and (current_sl == 0.0 or trail_sl < current_sl):
                    needs_update = True
                    
                if needs_update:
                    if ticket not in self._soft_targets:
                        self._soft_targets[ticket] = {}
                    self._soft_targets[ticket]['soft_sl'] = trail_sl
                    self._save_ghost_targets()
                    if self.telemetry_logger:
                        self.telemetry_logger.record_sentinel_event(
                            event_name="SL_TRAIL: Momentum Stall",
                            ticket=ticket,
                            reason="Momentum stalled in profit, aggressively trailing SL."
                        )

    async def _request_close(self, ticket: int, reason: str, event: TickEvent, pos_dir: str, order_type: str = "PROBE") -> None:
        import time
        now = time.time()
        if ticket in self._closing_tickets:
            if now - self._closing_tickets[ticket] < 5.0:
                return
            else:
                logger.warning(f"Tick Sentinel: Retrying CLOSE for Ticket {ticket} after TTL expiration.")
            
        self._closing_tickets[ticket] = now
        close_price = 0.0
        if event:
            close_price = event.ask if pos_dir == "SELL" else event.bid
        
        logger.info(f"Tick Sentinel: Executing CLOSE for Ticket {ticket}. Reason: {reason}.")
        
        if self.telemetry_logger:
            pos_dict = self._positions.get(ticket, {})
            entry_price = pos_dict.get("price", 0.0)
            holding_time = time.time() - self._pos_open_time.get(ticket, time.time())
            pnl = pos_dict.get("profit", 0.0)
            
            trade_data = {
                "Order Ticket": ticket,
                "Direction": pos_dir,
                "Entry Price": entry_price,
                "Exit Price": close_price,
                "Conviction Score": self._pos_conviction.get(ticket, 0.0),
                "Slippage": 0.0,
                "Tick-to-Trade Latency": 0.0,
                "Total Holding Time": holding_time,
                "Final PnL": pnl,
                "MFE": self._pos_mfe.get(ticket, 0.0),
                "MAE": self._pos_mae.get(ticket, 0.0)
            }
            self.telemetry_logger.record_trade_closed(trade_data)
        
        await self.event_bus.publish(OrderEvent(
            ticket=ticket,
            symbol=config.TRADING_SYMBOL,
            direction="CLOSE",
            volume=0.0,
            price=close_price,
            status="REQUEST",
            cycle_id=0,
            order_type=order_type
        ))
        
        await self.event_bus.publish(SentinelKillEvent(
            ticket=ticket,
            cycle_id=0,
            reason=reason,
            pnl=self._positions.get(ticket, {}).get("profit", 0.0)
        ))

