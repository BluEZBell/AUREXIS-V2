from typing import Any, Dict, List, Optional, Tuple, Union, Callable
import asyncio
import logging
import time
import numpy as np
import MetaTrader5 as mt5

from src.core.event_bus import EventBus, TickEvent, SignalEvent
import src.core.config as config
from src.core.config import run_mt5_task
from src.core.math_engine import calc_ema, calc_atr, calc_rsi, calc_adx, calc_macd, calc_bollinger_bands, calc_bbw_and_slope

from src.core.alpha import AlphaScorer
from src.execution.risk_manager import RiskManager
from src.execution.tick_sentinel import TickSentinel
from src.execution.bridge import MT5Bridge
from src.core.campaign_ledger import CampaignLedger
from src.core.news_filter import NewsFilter

logger = logging.getLogger("alpha_harvester")

class PreFlightDiagnostic:
    @staticmethod
    async def run(symbol: str) -> bool:
        logger.info("Running Pre-Flight Terminal Diagnostic...")
        
        terminal_info = await run_mt5_task(mt5.terminal_info)
        if terminal_info is None or not terminal_info.connected:
            logger.critical("Pre-Flight Diagnostic Failed: MT5 Terminal not connected to the broker server.")
            return False
            
        symbol_info = await run_mt5_task(mt5.symbol_info, symbol)
        if symbol_info is None:
            logger.critical(f"Pre-Flight Diagnostic Failed: Symbol {symbol} not found.")
            return False
            
        if not symbol_info.visible:
            logger.info(f"Symbol {symbol} is not visible, attempting to select it in Market Watch...")
            if not await run_mt5_task(mt5.symbol_select, symbol, True):
                logger.critical(f"Pre-Flight Diagnostic Failed: Could not select symbol {symbol} in Market Watch.")
                return False
                
        logger.info(f"Symbol {symbol} found. Tick Size: {symbol_info.trade_tick_size}, Point Value: {symbol_info.point}")
        
        account_info = await run_mt5_task(mt5.account_info)
        if account_info is None:
            logger.critical("Pre-Flight Diagnostic Failed: Could not retrieve account info.")
            return False
            
        if account_info.margin_free <= 0.0:
            logger.critical(f"Pre-Flight Diagnostic Failed: Insufficient Free Margin. Margin Free: {account_info.margin_free}")
            return False
            
        logger.info(f"Pre-Flight Diagnostic Passed. Free Margin: {account_info.margin_free}")
        return True

class WarmupSequence:
    @staticmethod
    async def run(symbol: str, alpha_scorer: AlphaScorer) -> bool:
        logger.info(f"Initiating Warm-Up Sequence for {symbol}...")
        
        warmup_success = await alpha_scorer.warmup(symbol)
        if not warmup_success:
            logger.critical("Warm-Up Sequence Failed: Could not initialize indicators or regime.")
            return False
            
        logger.info("Warm-Up Sequence Completed successfully.")
        return True

class DataIntegrityFilter:
    def __init__(self) -> None:
        self._last_valid_bid: Optional[float] = None
        self._clock_offset: Optional[int] = None

    async def validate_tick(self, tick: Any, current_atr: float) -> bool:
        if tick.bid <= 0.0 or tick.ask <= 0.0:
            logger.warning(f"REJECTED: Null or Zero pricing (Bid: {tick.bid}, Ask: {tick.ask})")
            return False
            
        if tick.bid >= tick.ask:
            logger.warning(f"REJECTED: Negative or Zero Spread (Bid: {tick.bid} >= Ask: {tick.ask})")
            return False
            
        self._last_valid_bid = float(tick.bid)
        return True


class AlphaHarvesterStrategy:
    MAX_ALLOWABLE_SPREAD = 500.0

    def __init__(self, event_bus: EventBus, risk_manager: RiskManager, execution_bridge: MT5Bridge, tick_sentinel: TickSentinel, alpha_scorer: AlphaScorer, campaign_ledger: CampaignLedger, telemetry_state=None, news_filter=None, tick_vault=None):
        self.event_bus = event_bus
        self.risk_manager = risk_manager
        self.execution_bridge = execution_bridge
        self.tick_sentinel = tick_sentinel
        self.alpha_scorer = alpha_scorer
        self.campaign_ledger = campaign_ledger
        self.telemetry_state = telemetry_state
        self.news_filter = news_filter
        self.tick_vault = tick_vault
        
        self.strategy_id = "CENTRAL_ORCHESTRATOR"
        self._running = False
        self.auto_sniper = True  # DEFAULT ARMED STATE
        
        from src.core.event_bus import CommandEvent
        self.event_bus.subscribe(CommandEvent, self.process_command)
        self._last_tick_time = 0
        self._last_tick_bid = 0.0
        self.data_filter = DataIntegrityFilter()

    async def process_command(self, event) -> None:
        if getattr(event, 'action', '') == "TOGGLE_AUTO_SNIPER":
            self.auto_sniper = not self.auto_sniper
            logger.info(f"Auto-Sniper {'ENGAGED' if self.auto_sniper else 'DISENGAGED'}")

    async def _handle_signal_execution(self, symbol: str, bid: float, ask: float, tick_ingest_time: float = 0.0):
        try:
            # Delegate all indicator fetching and evaluation to AlphaScorer
            signal = await self.alpha_scorer.evaluate_tick(symbol, bid, ask)
            self.current_score = signal.conviction_score
            logger.info(f"DEBUG HARVESTER RECEIVED SIGNAL: dir={signal.direction}, score={signal.conviction_score}")
            
            from src.core.event_bus import StrategyStateEvent
            
            # Determine cycle state directly from the ledger's active cycles
            is_active = hasattr(self, 'campaign_ledger') and self.campaign_ledger and getattr(self.campaign_ledger, 'active_cycles', None)
            
            asyncio.create_task(self.event_bus.publish(StrategyStateEvent(
                strategy_id=self.strategy_id,
                cycle_state="ACTIVE" if is_active else "IDLE",
                swarm_type="CORE",
                scout_dir="NONE",
                whipsaw_locked=False,
                whipsaw_locked_until=0.0,
                current_score=self.current_score
            )))

            
            if tick_ingest_time > 0:
                process_latency_ms = (time.perf_counter() - tick_ingest_time) * 1000.0
                if getattr(self, 'telemetry_state', None):
                    self.telemetry_state.processing_latency_ms = process_latency_ms
            
            if signal.action == "EXHAUSTION" or signal.regime == "EXHAUSTION":
                from src.core.event_bus import OrderEvent
                logger.info(f"Exhaustion detected. Issuing CLOSE events for {symbol}.")
                open_positions = await run_mt5_task(lambda: mt5.positions_get(symbol=symbol))
                if open_positions:
                    for pos in open_positions:
                        close_event = OrderEvent(
                            ticket=pos.ticket,
                            symbol=symbol,
                            direction="CLOSE",
                            volume=pos.volume,
                            price=bid,
                            status="REQUEST"
                        )
                        asyncio.create_task(self.event_bus.publish(close_event))
                
            if signal.conviction_score >= 50.0 and signal.direction != "NONE":
                logger.info(f"AlphaHarvester Execution Trace - Received Signal Score: {signal.conviction_score:.2f} Dir: {signal.direction}")

            # Operation: HFT Aggression - Eradicate Conservative Hardcodes
            # Trust the dynamic conviction score emitted by AlphaScorer and AdaptiveTuner
            if signal.direction in ["BUY", "SELL"]:
                logger.info(f"Micro-Breakout trigger evaluated. Conviction: {signal.conviction_score:.2f} | Regime: {signal.regime} | Requesting quota.")
                
                acc_info = await run_mt5_task(mt5.account_info)
                eq = acc_info.equity if acc_info else 0.0
                atr_m15 = getattr(self.alpha_scorer, '_last_atr', 200.0) # alpha scorer can track this
                
                lot_size = await self.risk_manager.calculate_lot_size(
                    equity=eq, 
                    atr=signal.atr, 
                    conviction=signal.conviction_score, 
                    oracle_probability=getattr(signal, 'probability', 0.0), 
                    regime=signal.regime, 
                    mtf_volume_confirmed=signal.mtf_volume_confirmed
                )
                
                if lot_size > 0:
                    logger.info(f"Risk Quota Approved: {lot_size} lots. Evaluated for Twin-Ticket split.")
                    
                    if True:
                        ratio_A = 0.4 if signal.regime in ["STRONG_TREND_BULL", "STRONG_TREND_BEAR"] else 1.0 if signal.regime == "RANGE" else 0.5
                        sym_info = mt5.symbol_info(symbol)
                        vol_step = getattr(sym_info, 'volume_step', 0.01) if sym_info else 0.01
                        
                        # If lot_size is only 0.01, we cannot split it. Send it all to Harvester (Ticket A).
                        if lot_size < 0.02:
                            vol_A = lot_size
                            vol_B = 0.0
                        else:
                            vol_A = lot_size if ratio_A == 1.0 else max(vol_step, round((lot_size * ratio_A) / vol_step) * vol_step)
                            vol_B = 0.0 if ratio_A == 1.0 else max(0.0, round(lot_size - vol_A, 2))
                            if vol_B > 0.0 and vol_B < vol_step:
                                vol_B = vol_step
                                vol_A = max(vol_step, round(lot_size - vol_B, 2))
                        
                        logger.info(f"Splitting {lot_size} into Ticket A (Harvester): {vol_A} and Ticket B (Runner): {vol_B}")
                        
                        price_entry = ask if signal.direction == "BUY" else bid
                        
                        point = 0.00001
                        sym_info = mt5.symbol_info(symbol)
                        if sym_info:
                            point = sym_info.point
                        
                        # TASK 2: FRICTION-ADAPTIVE HARVESTER TARGET
                        # Guarantee cash flow realization before 0.5 ATR Break-Even sweep, while explicitly overriding it if friction zone is too wide
                        spread_points = (ask - bid) / point if point > 0 else 0.0
                        minimum_friction_points = spread_points + 20.0
                        tp_distance_points = max(signal.atr * 2.0, minimum_friction_points * 3.0)
                        
                        if signal.direction == "BUY":
                            harvester_tp = price_entry + (tp_distance_points * point)
                        else:
                            harvester_tp = price_entry - (tp_distance_points * point)
                        
                        sig_event_A = SignalEvent(
                            symbol=symbol,
                            direction=signal.direction,
                            strategy_id=self.strategy_id + "_HARVESTER",
                            price=price_entry,
                            conviction=signal.conviction_score,
                            volume=vol_A,
                            cycle_id=int(time.time()),
                            order_type="CORE",
                            regime=signal.regime,
                            mtf_volume_confirmed=signal.mtf_volume_confirmed,
                            generation_time=time.time(),
                            soft_sl=signal.initial_invalidation_level,
                            soft_tp=harvester_tp,
                            atr=signal.atr,
                            is_hyper_scale=getattr(signal, 'is_hyper_scale', False)
                        )
                        sig_event_B = SignalEvent(
                            symbol=symbol,
                            direction=signal.direction,
                            strategy_id=self.strategy_id + "_RUNNER",
                            price=price_entry,
                            conviction=signal.conviction_score,
                            volume=vol_B,
                            cycle_id=int(time.time()),
                            order_type="CORE",
                            regime=signal.regime,
                            mtf_volume_confirmed=signal.mtf_volume_confirmed,
                            generation_time=time.time(),
                            soft_sl=signal.initial_invalidation_level,
                            soft_tp=0.0, # TASK 3: RUNNER EXHAUSTION PROTECTION (Unbounded)
                            atr=signal.atr,
                            is_hyper_scale=getattr(signal, 'is_hyper_scale', False)
                        )
                        asyncio.create_task(self.event_bus.publish(sig_event_A))
                        if vol_B > 0.0:
                            asyncio.create_task(self.event_bus.publish(sig_event_B))
                    else:
                        sig_event = SignalEvent(
                            symbol=symbol,
                            direction=signal.direction,
                            strategy_id=self.strategy_id + "_HARVESTER",
                            price=ask if signal.direction == "BUY" else bid,
                            conviction=signal.conviction_score,
                            volume=lot_size,
                            cycle_id=int(time.time()),
                            order_type="CORE",
                            regime=signal.regime,
                            mtf_volume_confirmed=signal.mtf_volume_confirmed,
                            generation_time=time.time(),
                            soft_sl=signal.initial_invalidation_level,
                            soft_tp=signal.dynamic_target,
                            atr=signal.atr,
                            is_hyper_scale=getattr(signal, 'is_hyper_scale', False)
                        )
                        asyncio.create_task(self.event_bus.publish(sig_event))
                    
        except Exception as e:
            logger.error(f"Error in signal evaluation pipeline: {e}", exc_info=True)

    async def start(self):
        self._running = True
        logger.info("AlphaHarvester Central Orchestrator Router started.")
        
        if self.news_filter:
            asyncio.create_task(self.news_filter.start())
        await self.tick_sentinel.start()
        
        # PRE-FLIGHT DIAGNOSTIC
        diagnostic_passed = await PreFlightDiagnostic.run(config.TRADING_SYMBOL)
        if not diagnostic_passed:
            logger.critical("Pre-Flight Diagnostic Failed. Initiating graceful shutdown...")
            self.stop()
            return

        # STATE WARM-UP SEQUENCE
        warmup_passed = await WarmupSequence.run(config.TRADING_SYMBOL, self.alpha_scorer)
        if not warmup_passed:
            logger.critical("State Warm-up Sequence Failed. Initiating graceful shutdown...")
            self.stop()
            return
            
        logger.info("Transitioning to Live Tick Router...")
        
        # Fetch point size once
        symbol_info = await run_mt5_task(mt5.symbol_info, config.TRADING_SYMBOL)
        point = symbol_info.point if symbol_info else 0.001
        
        while self._running:
            try:
                tick_ingest_start = time.perf_counter()
                tick = await run_mt5_task(mt5.symbol_info_tick, config.TRADING_SYMBOL)
                if tick:
                    # Operation: Terminal Edge - Data Integrity Sanity Check (Bad Tick Filter)
                    if tick.bid >= tick.ask or tick.bid <= 0 or tick.ask <= 0:
                        logger.warning(f"BAD TICK REJECTED: Invalid spread/price anomaly (Bid: {tick.bid}, Ask: {tick.ask}).")
                        await asyncio.sleep(0.01)
                        continue
                        
                    if self._last_tick_bid > 0:
                        jump_points = abs(tick.bid - self._last_tick_bid) / point if point > 0 else 0
                        time_delta = (tick.time_msc - self._last_tick_time) / 1000.0 if self._last_tick_time > 0 else 1.0
                        
                        if jump_points > 500 and time_delta < 0.1:
                            logger.warning(f"CORRUPTED DATA SPIKE REJECTED: Price jumped {jump_points:.1f} points in {time_delta:.3f}s (Bid: {self._last_tick_bid} -> {tick.bid}).")
                            await asyncio.sleep(0.01)
                            continue
                            
                    self._last_tick_bid = tick.bid
                
                if tick and tick.time_msc > self._last_tick_time:
                    tick_time_sec = tick.time_msc / 1000.0
                    current_sys_time = time.time()
                    
                    if not hasattr(self, '_clock_offset'):
                        self._clock_offset = current_sys_time - tick_time_sec
                        logger.info(f"CALIBRATED CLOCK OFFSET: {self._clock_offset*1000:.1f}ms")
                        
                    adjusted_sys_time = current_sys_time - self._clock_offset
                    latency_s = adjusted_sys_time - tick_time_sec
                    
                    # Operation: HFT Aggression - True Latency Armor
                    if latency_s > 1.5:
                        # Log sparsely to avoid spam during latency spikes
                        if latency_s < 60.0:
                            logger.warning(f"LATENCY ARMOR: Stale tick rejected (Latency: {latency_s*1000:.1f}ms > 1500ms).")
                        await asyncio.sleep(0.5)
                        continue

                    self._last_tick_time = tick.time_msc
                    

                    # DataIntegrityFilter
                    atr_m15 = getattr(self.alpha_scorer, '_last_atr', 200.0)
                    is_valid = await self.data_filter.validate_tick(tick, atr_m15)
                    if not is_valid:
                        await asyncio.sleep(0.01)
                        continue
                    
                    tick_event = TickEvent(
                        symbol=config.TRADING_SYMBOL,
                        time=tick.time,
                        bid=tick.bid,
                        ask=tick.ask,
                        volume=float(getattr(tick, 'volume_real', 0.0) or getattr(tick, 'volume', 0.0) or 1.0),
                        flags=getattr(tick, 'flags', 0)
                    )
                    
                    # Concurrently broadcast tick data to AlphaScorer Pipeline
                    asyncio.create_task(self.event_bus.publish(tick_event))
                    
                    if getattr(self, 'tick_vault', None):
                        await self.tick_vault.record_tick(
                            timestamp=float(tick.time_msc),
                            bid=float(tick.bid),
                            ask=float(tick.ask),
                            spread=float(tick.ask - tick.bid),
                            volume=float(getattr(tick, 'volume_real', tick.volume))
                        )
                    
                    # TASK 2: PREEMPTIVE SIGNAL SUPPRESSION
                    if not getattr(self.execution_bridge, 'is_connected', True):
                        if getattr(self, 'telemetry_state', None):
                            self.telemetry_state.recent_latency = (time.time() * 1000) - tick.time_msc
                        await asyncio.sleep(0.01)
                        continue
                    
                    current_spread = (tick.ask - tick.bid) / point
                    
                    # Bypass SpreadBlackout and NewsFilter
                    spread_blackout = False
                    news_blackout = False
                    
                    if not spread_blackout and not news_blackout:
                        if self.auto_sniper:
                            asyncio.create_task(self._handle_signal_execution(config.TRADING_SYMBOL, tick.bid, tick.ask, tick_ingest_start))
                    
                    if getattr(self, 'telemetry_state', None):
                        self.telemetry_state.realtime_spread = current_spread
                        self.telemetry_state.spread_blackout = spread_blackout
                        self.telemetry_state.recent_latency = (time.time() * 1000) - tick.time_msc
                        self.telemetry_state.news_blackout_active = news_blackout
                        self.telemetry_state.news_blackout_time_left = self.news_filter.get_time_until_next_blackout() if self.news_filter else None
                    
                # Strict event-driven non-blocking yield
                await asyncio.sleep(0.01)
                
            except asyncio.CancelledError:
                logger.info("AlphaHarvester loop cancelled.")
                break
            except Exception as e:
                logger.error(f"Tick Router loop encountered error: {e}")
                await asyncio.sleep(0.01)

    def stop(self):
        self._running = False
