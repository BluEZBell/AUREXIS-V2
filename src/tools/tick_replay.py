import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import MetaTrader5 as mt5

import src.core.config as config
from src.core.alpha import AlphaScorer, RegimeRadar
from src.analytics.ml_oracle import MLOracle
from src.core.event_bus import EventBus, TickEvent, SentinelKillEvent
from src.execution.tick_sentinel import TickSentinel
from src.core.campaign_ledger import CampaignLedger

logger: logging.Logger = logging.getLogger("tick_replay")
if not logger.handlers:
    handler: logging.StreamHandler = logging.StreamHandler()
    formatter: logging.Formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

async def ingest_historical_ticks(symbol: str, count: int = 100000) -> Any:
    """
    TASK 1: HISTORICAL TICK INGESTION
    Implement an async function using MetaTrader5.copy_ticks_from to download 
    at least the last 100,000 ticks for a target symbol.
    """
    logger.info(f"Initializing MT5 for tick ingestion ({symbol})...")
    if not mt5.initialize(path=config.MT5_TERMINAL_PATH):
        logger.error(f"Failed to initialize MT5: {mt5.last_error()}")
        return None

    logger.info(f"Downloading {count} ticks for {symbol}...")
    # Using copy_ticks_from with a historical date to fulfill the directive
    date_from: datetime = datetime.now() - timedelta(days=30)
    ticks: Any = mt5.copy_ticks_from(symbol, date_from, count, mt5.COPY_TICKS_ALL)
    
    if ticks is None:
        logger.error(f"Failed to fetch ticks from MT5: {mt5.last_error()}")
        return None
        
    logger.info(f"Successfully downloaded {len(ticks)} ticks.")
    return ticks

class DummyRiskManager:
    """Mock RiskManager required by TickSentinel instantiation."""
    def __init__(self):
        self.active_risk_tickets = set()
        self.protected_tickets = set()
        self.free_roll_recycles = 0
        
    async def calculate_lot_size(self, *args: Any, **kwargs: Any) -> float:
        if len(self.active_risk_tickets) >= 1:
            logger.info("RiskManager: Quota exhausted. Awaiting Free-Roll Pyramiding break-even to unlock more risk.")
            return 0.0
        return 1.0

    def release_quota(self, ticket: int):
        self.protected_tickets.add(ticket)
        if ticket in self.active_risk_tickets:
            self.active_risk_tickets.remove(ticket)
            self.free_roll_recycles += 1
        logger.info(f"Risk quota instantly released for ticket {ticket}. Free-Roll Pyramiding unlocked.")

def get_score_breakdown(ind: Dict[str, Any], direction: str, regime: str, bid: float) -> tuple[float, float, float]:
    macro, micro, vol = 0.0, 0.0, 0.0
    bb_lower = float(ind.get('bb_lower', 0.0))
    bb_upper = float(ind.get('bb_upper', 0.0))
    ema20_m5 = float(ind.get('ema20_m5', 0.0))
    
    if direction == "BUY":
        if regime == "STRONG_TREND_BULL": macro = 40.0
        elif regime in ("RANGE", "EXHAUSTION") and bid <= bb_lower: macro = 40.0
        if ema20_m5 > 0 and bid > ema20_m5: micro = 30.0
    elif direction == "SELL":
        if regime == "STRONG_TREND_BEAR": macro = 40.0
        elif regime in ("RANGE", "EXHAUSTION") and bid >= bb_upper: macro = 40.0
        if ema20_m5 > 0 and bid < ema20_m5: micro = 30.0

    m5_tick_vol_curr = float(ind.get('m5_tick_vol_curr', 0.0))
    m5_tick_vol_sma10 = float(ind.get('m5_tick_vol_sma10', 1.0))
    if m5_tick_vol_sma10 == 0: m5_tick_vol_sma10 = 1.0
    if m5_tick_vol_curr > m5_tick_vol_sma10 * 1.1:
        vol = 20.0
        
    return macro, micro, vol

async def run_replay_engine(symbol: str) -> None:
    """
    TASK 2 & 3: HIGH-SPEED ASYNC SIMULATION LOOP & PRECISION AUDIT
    """
    ticks: Any = await ingest_historical_ticks(symbol, 100000)
    if ticks is None or len(ticks) == 0:
        logger.error("No ticks to replay. Aborting.")
        return

    # Initialize Core Engines
    event_bus: EventBus = EventBus()
    radar: RegimeRadar = RegimeRadar(event_bus)
    oracle: MLOracle = MLOracle(event_bus)
    alpha_scorer: AlphaScorer = AlphaScorer(radar, oracle, event_bus)
    campaign_ledger: CampaignLedger = CampaignLedger(event_bus)
    campaign_ledger.db_path = ":memory:"
    await campaign_ledger.initialize()
    
    risk_manager: DummyRiskManager = DummyRiskManager()
    
    tick_sentinel: TickSentinel = TickSentinel(event_bus, risk_manager, campaign_ledger)
    
    await tick_sentinel.start()
    
    # Subscribe to SentinelKillEvent to complete the SAR simulation loop
    momentum_exhaustion_exits = 0
    
    async def on_kill(event):
        nonlocal momentum_exhaustion_exits
        logger.info(f"TickReplay: SentinelKillEvent received for ticket {event.ticket} with reason: {event.reason}. Removing from simulation.")
        if event.reason in ("MOMENTUM_REVERSAL", "GHOST_SL_HIT") and getattr(event, 'pnl', 0) > 0:
            momentum_exhaustion_exits += 1
            
        if event.ticket in simulated_positions:
            del simulated_positions[event.ticket]
            from src.core.event_bus import OrderEvent
            await event_bus.publish(OrderEvent(
                ticket=event.ticket, symbol=symbol, direction="CLOSE", 
                volume=0.0, price=0.0, status="CLOSED_SYNC", cycle_id=event.cycle_id
            ))
            
    event_bus.subscribe(SentinelKillEvent, on_kill)
    
    logger.info("Warming up AlphaScorer...")
    warmup_success: bool = await alpha_scorer.warmup(symbol)
    if not warmup_success:
        logger.error("AlphaScorer warmup failed. Aborting replay.")
        tick_sentinel.stop()
        return

    logger.info("Starting High-Speed Async Simulation Loop (Max Throughput)...")
    
    start_time: float = time.perf_counter()
    max_conviction: float = 0.0
    highest_score_details: Dict[str, Any] = {}
    triggered: bool = False
    
    simulated_positions = {}
    next_ticket = 1000
    
    bus_task = asyncio.create_task(event_bus.process_events())
    
    # Process ticks concurrently as fast as the CPU allows
    for i, tick in enumerate(ticks):
        tick_time: int = int(tick['time'])
        bid: float = float(tick['bid'])
        ask: float = float(tick['ask'])
        volume: float = float(tick['volume_real'] if 'volume_real' in tick.dtype.names else tick['volume'])
        
        tick_event: TickEvent = TickEvent(
            symbol=symbol,
            time=tick_time,
            bid=bid,
            ask=ask,
            volume=volume
        )
        
        # Concurrently process tick through sentinel and alpha scorer
        results = await asyncio.gather(
            tick_sentinel.process_tick(tick_event),
            alpha_scorer.evaluate_tick(symbol, bid, ask)
        )
        signal: Any = results[1]
        
        if signal.conviction_score > max_conviction:
            max_conviction = signal.conviction_score
            ind_state = getattr(alpha_scorer, '_last_ind', None)
            
            macro, micro, vol = 0.0, 0.0, 0.0
            if ind_state:
                macro, micro, vol = get_score_breakdown(ind_state, signal.direction, signal.regime, bid)
                
            highest_score_details = {
                "timestamp": tick_time,
                "price": bid,
                "direction": signal.direction,
                "conviction": signal.conviction_score,
                "regime": signal.regime,
                "macro": macro,
                "micro": micro,
                "volume": vol
            }
            
        # Simulate Execution and Pyramiding
        if signal.conviction_score >= 85.0:
            if not triggered:
                dt_str: str = datetime.fromtimestamp(tick_time).strftime('%Y-%m-%d %H:%M:%S')
                ind_state = getattr(alpha_scorer, '_last_ind', None)
                macro, micro, vol = 0.0, 0.0, 0.0
                if ind_state:
                    macro, micro, vol = get_score_breakdown(ind_state, signal.direction, signal.regime, bid)
                    
                logger.info(f"SUCCESSFUL TRIGGER | Time: {dt_str} | Price: {bid:.5f} | Dir: {signal.direction} | Conviction: {signal.conviction_score:.2f} | Breakdown: Macro={macro:.1f}, Micro={micro:.1f}, Volume={vol:.1f}")
                triggered = True

            lot = await risk_manager.calculate_lot_size()
            if lot > 0:
                ticket = next_ticket
                next_ticket += 1
                pos_dir = signal.direction
                pos_price = bid if pos_dir == "BUY" else ask
                pos = {
                    'ticket': ticket,
                    'symbol': symbol,
                    'type': pos_dir,
                    'volume': lot,
                    'price': pos_price,
                    'profit': 0.0,
                    'sl': 0.0,
                    'magic': config.MAGIC_NUMBER,
                    'price_current': pos_price,
                    'time': tick_time
                }
                simulated_positions[ticket] = pos
                risk_manager.active_risk_tickets.add(ticket)
                logger.info(f"SIMULATED EXECUTION (Pyramiding) | Ticket {ticket} | Dir: {pos_dir} | Price: {pos_price:.5f}")
                
                from src.core.event_bus import OrderEvent
                await event_bus.publish(OrderEvent(
                    ticket=ticket, symbol=symbol, direction=pos_dir, volume=lot, 
                    price=pos_price, status="FILLED", cycle_id=1, order_type="PROBE"
                ))
        
        # Simulate MTF Structural Trend Inversion (SAR test)
        if len(simulated_positions) > 0 and i % 5000 == 0:
            active_dir = list(simulated_positions.values())[0]['type']
            inv_trend = "BEARISH" if active_dir == "BUY" else "BULLISH"
            logger.info(f"Simulating MTF Structural Trend Inversion: {inv_trend} to test SAR")
            from src.core.event_bus import StructuralTrendEvent
            await event_bus.publish(StructuralTrendEvent(
                symbol=symbol, m15_trend=inv_trend, h1_trend="NEUTRAL", m15_close=bid, time=tick_time, m15_atr=20.0
            ))
            
        # Update PnL for simulated positions
        to_remove = []
        for tkt, p in simulated_positions.items():
            if tkt in tick_sentinel._closing_tickets:
                to_remove.append(tkt)
                continue
            point = 0.00001
            current = bid if p['type'] == "BUY" else ask
            p['price_current'] = current
            if p['type'] == "BUY":
                p['profit'] = (current - p['price']) / point
            else:
                p['profit'] = (p['price'] - current) / point
                
        for tkt in to_remove:
            del simulated_positions[tkt]
            from src.core.event_bus import OrderEvent
            await event_bus.publish(OrderEvent(
                ticket=tkt, symbol=symbol, direction="CLOSE", 
                volume=0.0, price=0.0, status="CLOSED_SYNC", cycle_id=1
            ))
            
        if simulated_positions:
            from src.core.event_bus import PositionsUpdateEvent
            await event_bus.publish(PositionsUpdateEvent(list(simulated_positions.values())))
            
        # Guarantee synchronization without using asyncio.sleep throttles 
        # to ensure TickSentinel and EventBus don't race/starve
        if event_bus._queue.qsize() > 0 or len(simulated_positions) > 0:
            for _ in range(3):
                dummy = asyncio.Future()
                asyncio.get_event_loop().call_soon(dummy.set_result, None)
                await dummy

    event_bus.stop()
    await bus_task

            
    elapsed: float = time.perf_counter() - start_time
    logger.info(f"Replay Engine finished. Processed {len(ticks)} ticks in {elapsed:.3f} seconds.")
    
    if not triggered:
        logger.info(f"STATISTICAL SUMMARY: No trades triggered. Max Conviction Reached: {max_conviction:.2f}")
        if highest_score_details:
            dt_max: str = datetime.fromtimestamp(highest_score_details["timestamp"]).strftime('%Y-%m-%d %H:%M:%S')
            
            macro = highest_score_details["macro"]
            micro = highest_score_details["micro"]
            vol = highest_score_details["volume"]
            
            failed_phase = "Unknown"
            if macro == 0.0: failed_phase = "Macro"
            elif micro == 0.0: failed_phase = "Micro"
            elif vol == 0.0: failed_phase = "Volume"
            else: failed_phase = "ML Oracle"
            
            logger.info(f"Max Conviction State: Time={dt_max}, Price={highest_score_details['price']:.5f}, "
                        f"Dir={highest_score_details['direction']}, Regime={highest_score_details['regime']} "
                        f"- Failed primarily at {failed_phase} phase (Macro: {macro:.1f}, Micro: {micro:.1f}, Volume: {vol:.1f})")

    print("\n" + "=" * 60)
    print(" " * 15 + "INSTITUTIONAL READINESS AUDIT")
    print("=" * 60)
    print(f" Total Ticks Processed       : {len(ticks)}")
    print(f" Free-Roll Recycles          : {risk_manager.free_roll_recycles}")
    print(f" Momentum Exhaustion Exits   : {momentum_exhaustion_exits}")
    print("=" * 60 + "\n")

    tick_sentinel.stop()

if __name__ == "__main__":
    target_symbol: str = getattr(config, 'TRADING_SYMBOL', "XAUUSD")
    asyncio.run(run_replay_engine(target_symbol))
