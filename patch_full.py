import sys

content = '''import numpy as np
import time
import MetaTrader5 as mt5
import asyncio
from src.core.event_bus import (
    EventBus, TickEvent, SignalEvent, CommandEvent, OrderEvent, 
    TargetHitEvent, ScoutSuccessEvent, ScoutFailEvent, SpikeDetectedEvent,
    MacroUpdateEvent, StructuralTrendEvent
)
from src.strategy.base_strategy import BaseStrategy
from src.core.math_engine import calc_ema, calc_atr, calc_rsi, calc_adx, calc_macd, calc_bollinger_bands
from src.core.config import setup_logger, run_mt5_task
import src.core.config as config
from src.core.campaign_ledger import CampaignLedger

logger = setup_logger("alpha_harvester")

class AlphaHarvesterStrategy(BaseStrategy):
    def __init__(self, event_bus: EventBus, risk_manager, campaign_ledger: CampaignLedger):
        super().__init__(event_bus)
        self.strategy_id = "INSTITUTIONAL_DESK_V5"
        self.risk_manager = risk_manager
        self.campaign_ledger = campaign_ledger
        
        from src.analytics.ml_oracle import MLOracle
        self.oracle = MLOracle()
        
        self.auto_sniper = True
        self.current_score = 50.0
        self._cooldown_until = 0.0
        self._last_tick_eval = 0.0
        self._latest_indicators = {}
        
        # Macro & Structure caches
        self._macro_history = []
        self._latest_structure = None
        
        # Whipsaw detection
        self.dir_changes = [] 
        self.whipsaw_locked_until = 0.0
        
        # Subscriptions
        self.event_bus.subscribe(CommandEvent, self.process_command)
        self.event_bus.subscribe(TickEvent, self.process_tick)
        self.event_bus.subscribe(TargetHitEvent, self.handle_target_hit)
        self.event_bus.subscribe(ScoutSuccessEvent, self.handle_scout_success)
        self.event_bus.subscribe(ScoutFailEvent, self.handle_scout_fail)
        self.event_bus.subscribe(SpikeDetectedEvent, self.handle_spike)
        self.event_bus.subscribe(MacroUpdateEvent, self.handle_macro_update)
        self.event_bus.subscribe(StructuralTrendEvent, self.handle_structural_trend)
        
        logger.info(f"{self.strategy_id} initialized with Event-Driven State Machine & Regime Radar.")

    async def process_command(self, event: CommandEvent):
        if event.action == "TOGGLE_AUTO_SNIPER":
            self.auto_sniper = not self.auto_sniper
            
        elif event.action == "WARNING_STOP_ADD":
            if event.payload and "cycle_id" in event.payload:
                cycle_id = event.payload["cycle_id"]
                cycle = self.campaign_ledger.get_cycle(cycle_id)
                if cycle and (cycle.state == "SWARM_FOLLOW" or cycle.state == "SWARM_REVERSE" or cycle.state == "SCOUT_ACTIVE"):
                    logger.warning(f"Harvester: Received WARNING_STOP_ADD for Cycle {cycle_id}. Halting SETs and transitioning to WARNING_WAIT.")
                    cycle.state = "WARNING_WAIT"
                    await self.campaign_ledger.save_cycle(cycle)

    async def handle_macro_update(self, event: MacroUpdateEvent):
        if not event.is_historical:
            self._macro_history.append(event)
            if len(self._macro_history) > 10:
                self._macro_history.pop(0)

    async def handle_structural_trend(self, event: StructuralTrendEvent):
        self._latest_structure = event

    async def _calculate_conviction(self, direction: str, chop_score: int = 0) -> float:
        score = 0.0
        
        ind = self._latest_indicators.get(config.TRADING_SYMBOL)
        if not ind:
            return 0.0
            
        curr_price = ind.get('curr_price', 0.0)
        ema20_m15 = ind.get('ema20_m15', 0.0)
        ema50_m15 = ind.get('ema50_m15', 0.0)
        rsi = ind.get('rsi', 50.0)
        bb_upper = ind.get('bb_upper', 0.0)
        bb_lower = ind.get('bb_lower', 0.0)
        adx_m15 = ind.get('adx_m15', 0.0)
        macd_hist = ind.get('macd_hist', 0.0)
        
        if chop_score < 3:
            # PATH A: Trend Mode
            if direction == "BUY":
                if ema20_m15 > 0 and curr_price <= ema20_m15 * 1.0005 and curr_price >= ema20_m15 * 0.9990 and 35 <= rsi <= 58:
                    score += 50.0
                elif curr_price > ema20_m15 and macd_hist > 0 and rsi > 55:
                    score += 70.0
                    
                if rsi > 60:
                    score -= 100.0
                if macd_hist < 0 and rsi < 45:
                    score -= 100.0
            else:
                if ema20_m15 > 0 and curr_price >= ema20_m15 * 0.9995 and curr_price <= ema20_m15 * 1.0010 and 42 <= rsi <= 65:
                    score += 50.0
                elif curr_price < ema20_m15 and macd_hist < 0 and rsi < 45:
                    score += 70.0
                    
                if rsi < 40:
                    score -= 100.0
                if macd_hist > 0 and rsi > 55:
                    score -= 100.0
                    
            if self._latest_structure:
                h1 = self._latest_structure.h1_trend
                m15 = self._latest_structure.m15_trend
                if direction == "BUY":
                    if h1 == "BULLISH" and m15 == "BULLISH":
                        score += 30.0
                    elif h1 == "BEARISH" or m15 == "BEARISH":
                        score -= 20.0
                else:
                    if h1 == "BEARISH" and m15 == "BEARISH":
                        score += 30.0
                    elif h1 == "BULLISH" or m15 == "BULLISH":
                        score -= 20.0
                        
            if adx_m15 > 22.0:
                if direction == "BUY" and macd_hist > 0:
                    score += 20.0
                elif direction == "SELL" and macd_hist < 0:
                    score += 20.0
        else:
            # PATH B: Range Mode
            if direction == "BUY":
                if curr_price <= bb_lower + (bb_upper - bb_lower) * 0.1 and rsi < 45:
                    score += 50.0
                if rsi > 50 or curr_price >= bb_upper - (bb_upper - bb_lower) * 0.1:
                    score -= 100.0
            else:
                if curr_price >= bb_upper - (bb_upper - bb_lower) * 0.1 and rsi > 55:
                    score += 50.0
                if rsi < 50 or curr_price <= bb_lower + (bb_upper - bb_lower) * 0.1:
                    score -= 100.0

        return max(0.0, min(100.0, score))
            
    async def get_indicators(self, symbol: str):
        # Fetch M5 and M15 data
        m5_rates = await run_mt5_task(lambda: mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100))
        m15_rates = await run_mt5_task(lambda: mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 50))
        if m5_rates is None or len(m5_rates) < 100 or m15_rates is None or len(m15_rates) < 50:
            return None
            
        m5_close = np.array([x['close'] for x in m5_rates])
        m5_high = np.array([x['high'] for x in m5_rates])
        m5_low = np.array([x['low'] for x in m5_rates])
        
        m15_close = np.array([x['close'] for x in m15_rates])
        m15_high = np.array([x['high'] for x in m15_rates])
        m15_low = np.array([x['low'] for x in m15_rates])
        
        # ATR M5
        atr_m5 = calc_atr(m5_high, m5_low, m5_close, 14)[-1]
        adx_m5 = calc_adx(m5_high, m5_low, m5_close, 14)[-1]
        rsi_m5 = calc_rsi(m5_close, 14)[-1]
        
        macd_line, macd_signal, macd_hist = calc_macd(m5_close, 12, 26, 9)
        
        ema20_m15 = calc_ema(m15_close, 20)[-1]
        ema50_m15 = calc_ema(m15_close, 50)[-1]
        
        # M15 Regime Math
        adx_m15 = calc_adx(m15_high, m15_low, m15_close, 14)[-1]
        bb_upper, bb_mid, bb_lower = calc_bollinger_bands(m15_close, 20, 2.0)
        
        # Structure break M5
        swing_high = np.max(m5_high[-6:-1])
        swing_low = np.min(m5_low[-6:-1])
        
        curr_price = m5_close[-1]
        bull_break = curr_price > swing_high + (0.20 * atr_m5)
        bear_break = curr_price < swing_low - (0.20 * atr_m5)
        
        # Chop Score Metrics
        m5_range_10 = np.max(m5_high[-10:]) - np.min(m5_low[-10:])
        atr_m15 = calc_atr(m15_high, m15_low, m15_close, 14)[-1]
        adx_series = calc_adx(m15_high, m15_low, m15_close, 14)
        adx_m15_rising = adx_series[-1] > adx_series[-2]
        ema_expansion = abs(ema20_m15 - ema50_m15) > 0.3 * atr_m15

        return {
            "atr": atr_m5,
            "adx": adx_m5,
            "rsi": rsi_m5,
            "macd_line": macd_line[-1],
            "macd_signal": macd_signal[-1],
            "macd_hist": macd_hist[-1],
            "ema20_m15": ema20_m15,
            "ema50_m15": ema50_m15,
            "adx_m15": adx_m15,
            "bb_upper": bb_upper[-1],
            "bb_lower": bb_lower[-1],
            "swing_high": swing_high,
            "swing_low": swing_low,
            "bull_break": bull_break,
            "bear_break": bear_break,
            "curr_price": curr_price,
            "m5_range_10": m5_range_10,
            "atr_m15": atr_m15,
            "adx_m15_rising": adx_m15_rising,
            "ema_expansion": ema_expansion
        }

    async def check_whipsaw_lock(self, ind):
        current_time = time.time()
        if current_time < self.whipsaw_locked_until:
            # Massive breakout un-locks
            if ind['adx'] >= 22 and (ind['bull_break'] or ind['bear_break']):
                self.whipsaw_locked_until = 0.0
                logger.info("Whipsaw lock lifted by strong ADX & Breakout")
                return False
            return True
        return False

    async def calculate_chop_score(self, ind):
        score = 0
        if ind['adx_m15'] < 18: score += 1
        if 45 <= ind['rsi'] <= 55: score += 1
        if abs(ind['ema20_m15'] - ind['ema50_m15']) < (0.15 * ind['atr_m15']): score += 1
        if ind['m5_range_10'] < (0.80 * ind['atr_m15']): score += 1
        if len(self.dir_changes) >= 3: score += 1
        return score
        
    async def calculate_breakout_score(self, ind):
        score = 0
        if ind['bull_break'] or ind['bear_break']: score += 1
        if ind['adx_m15'] > 20 and ind['adx_m15_rising']: score += 2
        if ind['rsi'] > 55 or ind['rsi'] < 45: score += 1
        if ind['ema_expansion']: score += 1
        return score

    async def log_direction_flip(self):
        current_time = time.time()
        self.dir_changes.append(current_time)
        self.dir_changes = [t for t in self.dir_changes if current_time - t < 3000] # roughly 10 M5 candles
        if len(self.dir_changes) >= 3:
            self.whipsaw_locked_until = current_time + 1800 # 30 min lock
            logger.warning("WHIPSAW LOCK ACTIVATED")

    async def process_tick(self, event: TickEvent):
        current_time = time.time()
        if current_time < self._cooldown_until or current_time - self._last_tick_eval < 1.0:
            return
        self._last_tick_eval = current_time
        
        try:
            ind = await self.get_indicators(event.symbol)
            if not ind: return
            self._latest_indicators[event.symbol] = ind
            
            chop_score = await self.calculate_chop_score(ind)
            breakout_score = await self.calculate_breakout_score(ind)
            
            active_cycles = list(self.campaign_ledger.active_cycles.values())
            
            if len(active_cycles) == 0 and self.auto_sniper:
                if await self.check_whipsaw_lock(ind):
                    return
                    
                # SCOUT Entry Logic (Omni-Directional Radar)
                conv_buy = await self._calculate_conviction("BUY", chop_score)
                conv_sell = await self._calculate_conviction("SELL", chop_score)
                
                direction = None
                conv = 0.0
                if conv_buy >= 40.0 and conv_buy > conv_sell:
                    direction = "BUY"
                    conv = conv_buy
                elif conv_sell >= 40.0 and conv_sell > conv_buy:
                    direction = "SELL"
                    conv = conv_sell
                    
                if not direction:
                    # Do not return yet, we must update telemetry
                    pass
                else:
                    cycle_id = int(time.time())
                    logger.info(f"SCOUT ENTRY: {direction}. Initializing Cycle {cycle_id} with Conviction: {conv}")
                    sig = SignalEvent(event.symbol, direction, self.strategy_id, event.bid, conviction=conv, volume=0.10, cycle_id=cycle_id, order_type="PROBE")
                    await self.event_bus.publish(sig)
                    self._cooldown_until = current_time + 2.0
                
            else:
                for cycle in active_cycles:
                    cycle.chop_score = chop_score
                    
                    num_pos = len(cycle.set_tickets) + (1 if cycle.probe_ticket else 0)
                    
                    if num_pos >= 3 and cycle.cycle_pnl < 0.0 and cycle.state not in ["HOLD_RECOVERY", "WAIT", "CLOSE_RECOVERY"]:
                        logger.warning(f"Cycle {cycle.cycle_id}: Full SET reached (3 positions) but P/L is negative. Transitioning to HOLD_RECOVERY.")
                        cycle.state = "HOLD_RECOVERY"
                        await self.campaign_ledger.save_cycle(cycle)
                        continue
                        
                    if cycle.state == "SWARM_FOLLOW" or cycle.state == "SWARM_REVERSE":
                        if num_pos == 2:
                            live_positions = await run_mt5_task(lambda c=cycle.direction: mt5.positions_get(symbol=config.TRADING_SYMBOL))
                            live_pos_count = len(live_positions) if live_positions else 0
                            
                            if live_pos_count == 2:
                                if cycle.state == "SWARM_FOLLOW" and ind['adx'] >= 22:
                                    conv = await self._calculate_conviction(cycle.direction, chop_score)
                                    if conv >= 50.0:
                                        logger.info(f"Cycle {cycle.cycle_id}: Opening 3rd SET (Follow). Conviction {conv}")
                                        sig = SignalEvent(event.symbol, cycle.direction, self.strategy_id, event.bid, conviction=conv, volume=0.0, cycle_id=cycle.cycle_id, order_type="SET")
                                        await self.event_bus.publish(sig)
                                        cycle.state = "SWARM_COMPLETE"
                                        await self.campaign_ledger.save_cycle(cycle)
                                        self._cooldown_until = current_time + 1.0
                                elif cycle.state == "SWARM_REVERSE" and ind['adx'] >= 22:
                                    conv = await self._calculate_conviction(cycle.direction, chop_score)
                                    if conv >= 50.0:
                                        logger.info(f"Cycle {cycle.cycle_id}: Opening 3rd SET (Reverse). Conviction {conv}")
                                        sig = SignalEvent(event.symbol, cycle.direction, self.strategy_id, event.bid, conviction=conv, volume=0.0, cycle_id=cycle.cycle_id, order_type="SET")
                                        await self.event_bus.publish(sig)
                                        cycle.state = "SWARM_COMPLETE"
                                        await self.campaign_ledger.save_cycle(cycle)
                                        self._cooldown_until = current_time + 1.0
                                    
                    elif cycle.state == "WARNING_WAIT":
                        if ind['adx'] >= 22.0:
                            conv = await self._calculate_conviction(cycle.direction, chop_score)
                            if conv >= 50.0:
                                logger.info(f"Cycle {cycle.cycle_id}: Momentum returned (ADX>=22, Conviction>50). Resuming SWARM from WARNING_WAIT.")
                                cycle.state = "SWARM_FOLLOW"
                                cycle.dispatched_events.discard("WARNING_STOP_ADD")
                                await self.campaign_ledger.save_cycle(cycle)
                                
                    elif cycle.state == "CLOSE_RECOVERY":
                        active_tickets = []
                        if cycle.probe_ticket:
                            pos = await run_mt5_task(lambda tk=cycle.probe_ticket: mt5.positions_get(ticket=tk))
                            if pos and len(pos) > 0: active_tickets.append(cycle.probe_ticket)
                        for st in cycle.set_tickets:
                            pos = await run_mt5_task(lambda tk=st: mt5.positions_get(ticket=tk))
                            if pos and len(pos) > 0: active_tickets.append(st)
                            
                        if not active_tickets:
                            logger.info(f"Cycle {cycle.cycle_id}: CLOSE_RECOVERY complete. All positions confirmed closed.")
                            cycle.state = "IDLE"
                            await self.campaign_ledger.save_cycle(cycle)
                        else:
                            logger.warning(f"Cycle {cycle.cycle_id}: CLOSE_RECOVERY - Retrying close for {len(active_tickets)} positions.")
                            tick = await run_mt5_task(lambda: mt5.symbol_info_tick(config.TRADING_SYMBOL))
                            price = tick.bid if cycle.direction == "BUY" else tick.ask
                            for tk in active_tickets:
                                await self.event_bus.publish(OrderEvent(tk, config.TRADING_SYMBOL, "CLOSE", 0.0, price, "REQUEST", cycle_id=cycle.cycle_id))
                            self._cooldown_until = current_time + 1.0

                    elif cycle.state not in ["WAIT", "CLOSE_RECOVERY"]:
                        reversal_detected = False
                        p_dir = cycle.direction
                        if p_dir == "BUY" and ind['bear_break'] and ind['rsi'] < 50:
                            reversal_detected = True
                        elif p_dir == "SELL" and ind['bull_break'] and ind['rsi'] > 50:
                            reversal_detected = True
                            
                        if reversal_detected:
                            logger.info(f"Cycle {cycle.cycle_id}: ADAPTIVE REVERSAL DETECTED. Closing all.")
                            cycle.state = "IDLE"
                            cycle.exit_reason = "ADAPTIVE_REVERSAL"
                            await self.campaign_ledger.save_cycle(cycle)
                            tick = await run_mt5_task(lambda: mt5.symbol_info_tick(event.symbol))
                            price = tick.bid if p_dir == "BUY" else tick.ask
                            if cycle.probe_ticket:
                                await self.event_bus.publish(OrderEvent(cycle.probe_ticket, event.symbol, "CLOSE", 0.0, price, "REQUEST", cycle_id=cycle.cycle_id))
                            for st in cycle.set_tickets:
                                await self.event_bus.publish(OrderEvent(st, event.symbol, "CLOSE", 0.0, price, "REQUEST", cycle_id=cycle.cycle_id))
                            
                            await self.log_direction_flip()
                            self._cooldown_until = current_time + 2.0

            # --- START TELEMETRY SURGICAL FIX ---
            # Omni-Directional Radar Telemetry Fix
            conv_buy = await self._calculate_conviction("BUY", chop_score)
            conv_sell = await self._calculate_conviction("SELL", chop_score)
            hypothetical_dir = "BUY" if conv_buy >= conv_sell else "SELL"
            self.current_score = max(conv_buy, conv_sell)
            
            global_state = "IDLE"
            swarm_type = "N/A"
            active_cycles = self.campaign_ledger.get_active_cycles()
            if active_cycles:
                primary_cycle = active_cycles[0]
                global_state = primary_cycle.state
                hypothetical_dir = primary_cycle.direction
                if primary_cycle.state in ["SWARM_FOLLOW", "SWARM_REVERSE", "SWARM_COMPLETE"]:
                    swarm_type = "FOLLOW" if primary_cycle.state == "SWARM_FOLLOW" else ("REVERSE" if primary_cycle.state == "SWARM_REVERSE" else "COMPLETE")
            else:
                global_state = "TREND_ACTIVE" if chop_score < 3 else "RANGE_ACTIVE"
                    
            from src.core.event_bus import StrategyStateEvent
            whipsaw_locked = await self.check_whipsaw_lock(ind)
            state_event = StrategyStateEvent(
                strategy_id=self.strategy_id,
                cycle_state=global_state,
                swarm_type=swarm_type,
                scout_dir=hypothetical_dir,
                whipsaw_locked=whipsaw_locked,
                whipsaw_locked_until=self.whipsaw_locked_until,
                current_score=self.current_score
            )
            await self.event_bus.publish(state_event)
            # --- END TELEMETRY SURGICAL FIX ---

        except Exception as e:
            logger.error(f"Harvester Tick Error: {e}")

    async def handle_target_hit(self, event: TargetHitEvent):
        logger.info(f"Harvester: Target Hit for Cycle {event.cycle_id}. Closing all and entering CLOSE_RECOVERY.")
        cycle = self.campaign_ledger.get_cycle(event.cycle_id)
        if cycle:
            cycle.state = "CLOSE_RECOVERY"
            cycle.exit_reason = "TARGET_HIT"
            await self.campaign_ledger.save_cycle(cycle)
            symbol = config.TRADING_SYMBOL
            tick = await run_mt5_task(lambda: mt5.symbol_info_tick(symbol))
            price = tick.bid if cycle.direction == "BUY" else tick.ask
            if cycle.probe_ticket:
                await self.event_bus.publish(OrderEvent(cycle.probe_ticket, symbol, "CLOSE", 0.0, price, "REQUEST", cycle_id=event.cycle_id))
            for st in cycle.set_tickets:
                await self.event_bus.publish(OrderEvent(st, symbol, "CLOSE", 0.0, price, "REQUEST", cycle_id=event.cycle_id))
            self._cooldown_until = time.time() + 1.0

    async def handle_scout_success(self, event: ScoutSuccessEvent):
        cycle = self.campaign_ledger.get_cycle(event.cycle_id)
        if not cycle or cycle.state != "SCOUT_ACTIVE": return
        cycle.state = "FOLLOW_SCORING"
        await self.campaign_ledger.save_cycle(cycle)
        
        symbol = config.TRADING_SYMBOL
        ind = self._latest_indicators.get(symbol)
        if not ind:
            ind = await self.get_indicators(symbol)
            if not ind: return
            
        p_dir = cycle.direction
        chop_score = await self.calculate_chop_score(ind)
        conviction_score = await self._calculate_conviction(p_dir, chop_score)
        
        if conviction_score >= 50.0:
            # Phase 10: The ML Inference Oracle Check
            point = 0.00001
            try:
                symbol_info = await run_mt5_task(lambda: mt5.symbol_info(symbol))
                tick = await run_mt5_task(lambda: mt5.symbol_info_tick(symbol))
                if symbol_info and tick:
                    point = symbol_info.point
                    spread_points = (tick.ask - tick.bid) / point
                else:
                    spread_points = 0.0
            except:
                spread_points = 0.0
                
            features = {
                "conviction_score": conviction_score,
                "dxy_val": self._macro_history[-1].dxy if self._macro_history else 0.0,
                "us10y_val": self._macro_history[-1].us10y if self._macro_history else 0.0,
                "m15_atr": self._latest_structure.m15_atr if self._latest_structure else 0.0,
                "spread_points": spread_points
            }
            
            prob = await self.oracle.predict_success_probability(features)
            if prob < 0.40:
                logger.warning(f"ML Oracle VETO: Probability ({prob:.2f}) too low. Denying SET escalation.")
                cycle.state = "SCOUT_ACTIVE"
                cycle.dispatched_events.discard("SCOUT_SUCCESS")
                await self.campaign_ledger.save_cycle(cycle)
                return

            logger.info(f"Harvester: Scout Success. Conviction: {conviction_score}. ML Prob: {prob:.2f}. Transitioning to SWARM_FOLLOW.")
            cycle.state = "SWARM_FOLLOW"
            await self.campaign_ledger.save_cycle(cycle)
            tick = await run_mt5_task(lambda: mt5.symbol_info_tick(symbol))
            price = tick.ask if p_dir == "BUY" else tick.bid
            sig = SignalEvent(symbol, p_dir, self.strategy_id, price, conviction=conviction_score, volume=0.0, cycle_id=event.cycle_id, order_type="SET")
            await self.event_bus.publish(sig)
            self._cooldown_until = time.time() + 1.0
        else:
            logger.info(f"Harvester: Conviction {conviction_score} too low for SET escalation. Reverting to SCOUT_ACTIVE.")
            cycle.state = "SCOUT_ACTIVE"
            cycle.dispatched_events.discard("SCOUT_SUCCESS")
            await self.campaign_ledger.save_cycle(cycle)

    async def handle_scout_fail(self, event: ScoutFailEvent):
        cycle = self.campaign_ledger.get_cycle(event.cycle_id)
        if not cycle or cycle.state != "SCOUT_ACTIVE": return
        cycle.state = "REVERSE_SCORING"
        await self.campaign_ledger.save_cycle(cycle)
        
        symbol = config.TRADING_SYMBOL
        ind = self._latest_indicators.get(symbol)
        if not ind:
            ind = await self.get_indicators(symbol)
            if not ind: return
            
        opp_dir = "SELL" if cycle.direction == "BUY" else "BUY"
        chop_score = await self.calculate_chop_score(ind)
        conviction_score = await self._calculate_conviction(opp_dir, chop_score)
        
        if conviction_score >= 50.0:
            # Phase 10: The ML Inference Oracle Check
            point = 0.00001
            try:
                symbol_info = await run_mt5_task(lambda: mt5.symbol_info(symbol))
                tick = await run_mt5_task(lambda: mt5.symbol_info_tick(symbol))
                if symbol_info and tick:
                    point = symbol_info.point
                    spread_points = (tick.ask - tick.bid) / point
                else:
                    spread_points = 0.0
            except:
                spread_points = 0.0
                
            features = {
                "conviction_score": conviction_score,
                "dxy_val": self._macro_history[-1].dxy if self._macro_history else 0.0,
                "us10y_val": self._macro_history[-1].us10y if self._macro_history else 0.0,
                "m15_atr": self._latest_structure.m15_atr if self._latest_structure else 0.0,
                "spread_points": spread_points
            }
            
            prob = await self.oracle.predict_success_probability(features)
            if prob < 0.40:
                logger.warning(f"ML Oracle VETO: Probability ({prob:.2f}) too low. Denying Reverse SET escalation.")
                cycle.state = "SCOUT_ACTIVE"
                cycle.dispatched_events.discard("SCOUT_FAIL")
                await self.campaign_ledger.save_cycle(cycle)
                return

            logger.info(f"Harvester: Reverse Confirmed. Conviction: {conviction_score}. ML Prob: {prob:.2f}. Closing old cycle and Chaining new PROBE.")
            await self.log_direction_flip()
            
            tick = await run_mt5_task(lambda: mt5.symbol_info_tick(symbol))
            close_price = tick.bid if opp_dir == "SELL" else tick.ask # Closing probe
            open_price = tick.ask if opp_dir == "BUY" else tick.bid
            
            if cycle.probe_ticket:
                await self.event_bus.publish(OrderEvent(cycle.probe_ticket, symbol, "CLOSE", 0.0, close_price, "REQUEST", cycle_id=event.cycle_id))
            for st in cycle.set_tickets:
                await self.event_bus.publish(OrderEvent(st, symbol, "CLOSE", 0.0, close_price, "REQUEST", cycle_id=event.cycle_id))
                
            # Close old cycle
            cycle.state = "IDLE"
            cycle.exit_reason = "SCOUT_FAIL"
            await self.campaign_ledger.save_cycle(cycle)
            
            # Chain new cycle
            new_cycle_id = int(time.time())
            sig = SignalEvent(symbol, opp_dir, self.strategy_id, open_price, conviction=conviction_score, volume=0.0, cycle_id=new_cycle_id, order_type="PROBE")
            await self.event_bus.publish(sig)
            
            self._cooldown_until = time.time() + 1.0
        else:
            logger.info(f"Harvester: Reverse Conviction {conviction_score} too low. Reverting to SCOUT_ACTIVE.")
            cycle.state = "SCOUT_ACTIVE"
            cycle.dispatched_events.discard("SCOUT_FAIL")
            await self.campaign_ledger.save_cycle(cycle)

    async def handle_spike(self, event: SpikeDetectedEvent):
        logger.warning(f"Harvester: Spike Protection for Cycle {event.cycle_id}. Halting SETs.")
        cycle = self.campaign_ledger.get_cycle(event.cycle_id)
        if cycle:
            cycle.state = "WAIT"
            await self.campaign_ledger.save_cycle(cycle)
'''

with open('src/strategy/alpha_harvester.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("AlphaHarvester Fully Overwritten successfully.")
