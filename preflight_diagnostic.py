import asyncio
import logging
import time
from typing import Optional, Any
from concurrent.futures import ThreadPoolExecutor
import MetaTrader5 as mt5
import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("PreFlight")

# Thread pool for MT5 calls with max_workers=1 to ensure thread-safe serial execution
executor = ThreadPoolExecutor(max_workers=1)

async def run_mt5_task(func, *args, **kwargs) -> Any:
    """Wrapper to run MT5 blocking calls in a thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))

async def init_mt5() -> bool:
    """Initialize MT5 connection."""
    initialized = await run_mt5_task(mt5.initialize)
    if not initialized:
        logger.error(f"MT5 initialization failed: {mt5.last_error()}")
    return initialized

async def shutdown_mt5():
    """Shutdown MT5 connection."""
    await run_mt5_task(mt5.shutdown)
    executor.shutdown(wait=True)

async def task1_latency_auditor(symbol: str = "XAUUSD") -> float:
    """TASK 1: Environment & Latency Auditor"""
    logger.info("[TASK 1: ENVIRONMENT & LATENCY AUDITOR]")
    logger.info("-" * 60)
    
    terminal_info = await run_mt5_task(mt5.terminal_info)
    if terminal_info is None:
        logger.error("Could not fetch terminal info.")
        return 9999.0
        
    # ping_last is typically in microseconds
    ping_ms = terminal_info.ping_last / 1000.0
    
    # Measure execution latency
    start_time = time.perf_counter()
    tick = await run_mt5_task(mt5.symbol_info_tick, symbol)
    rates = await run_mt5_task(mt5.copy_rates_from_pos, symbol, mt5.TIMEFRAME_M15, 0, 14)
    end_time = time.perf_counter()
    
    exec_latency_ms = (end_time - start_time) * 1000.0
    total_latency_ms = ping_ms + exec_latency_ms
    
    logger.info(f"{'Broker Ping Latency':<25}: {ping_ms:.2f} ms")
    logger.info(f"{'Terminal Exec Latency':<25}: {exec_latency_ms:.2f} ms")
    logger.info(f"{'Total Effective Latency':<25}: {total_latency_ms:.2f} ms")
    
    if total_latency_ms > 50.0:
        logger.critical(f"{'Status':<25}: FAILED (Latency > 50ms. Nano Break-Even compromised!)")
    else:
        logger.info(f"{'Status':<25}: PASSED (<= 50ms)")
        
    logger.info("-" * 60)
    return total_latency_ms

async def task2_margin_stress_test(symbol: str = "XAUUSD") -> bool:
    """TASK 2: $100 Account Margin Stress Test"""
    logger.info("[TASK 2: $100 ACCOUNT MARGIN STRESS TEST]")
    logger.info("-" * 60)
    
    account_info = await run_mt5_task(mt5.account_info)
    if account_info is None:
        logger.error("Could not fetch account info.")
        return False
        
    equity = account_info.equity
    leverage = account_info.leverage
    
    tick = await run_mt5_task(mt5.symbol_info_tick, symbol)
    if tick is None:
        logger.error(f"Could not fetch tick for {symbol}")
        return False
        
    volume = 0.01
    action = mt5.ORDER_TYPE_BUY
    margin_req = await run_mt5_task(mt5.order_calc_margin, action, symbol, volume, tick.ask)
    
    if margin_req is None:
        logger.error(f"Could not calculate margin for {symbol}")
        return False
        
    logger.info(f"{'Account Equity':<25}: ${equity:.2f}")
    logger.info(f"{'Account Leverage':<25}: 1:{leverage}")
    logger.info(f"{'Micro-lot Volume':<25}: {volume}")
    logger.info(f"{'Margin Required':<25}: ${margin_req:.2f}")
    
    if margin_req <= 0:
        logger.error("Margin requirement is 0 or negative. Invalid broker response.")
        return False
        
    capacity = int(equity / margin_req)
    logger.info(f"{'Max Swarm Capacity':<25}: {capacity} simultaneous positions")
    
    if capacity < 5:
        logger.critical(f"{'Status':<25}: FATAL ERROR (Account cannot support >= 5 micro-lots!)")
        logger.info("-" * 60)
        return False
    else:
        logger.info(f"{'Status':<25}: PASSED (>= 5 simultaneous micro-lots)")
        
    logger.info("-" * 60)
    return True

def calculate_atr(rates: Any, period: int = 14) -> float:
    """Calculate standard M15 ATR using Wilder's Smoothing."""
    if rates is None or len(rates) < period:
        return 0.0
    
    df = pd.DataFrame(list(rates))
    df['tr0'] = df['high'] - df['low']
    df['tr1'] = abs(df['high'] - df['close'].shift(1))
    df['tr2'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    
    # Wilder's Smoothing
    atr = df['tr'].ewm(alpha=1/period, adjust=False).mean().iloc[-1]
    
    if pd.isna(atr):
        return 0.0
    return float(atr)

async def task3_spread_friction_analysis(symbol: str = "XAUUSD") -> None:
    """TASK 3: Spread & Friction Analysis"""
    logger.info("[TASK 3: SPREAD & FRICTION ANALYSIS]")
    logger.info("-" * 60)
    
    symbol_info = await run_mt5_task(mt5.symbol_info, symbol)
    tick = await run_mt5_task(mt5.symbol_info_tick, symbol)
    
    if symbol_info is None or tick is None:
        logger.error(f"Could not fetch symbol info or tick for {symbol}")
        return
        
    swap_long = symbol_info.swap_long
    swap_short = symbol_info.swap_short
    spread_points = symbol_info.spread
    
    volume = 0.01
    contract_size = symbol_info.trade_contract_size
    spread_raw = tick.ask - tick.bid
    
    # Calculate friction cost by evaluating the immediate loss on a round-trip
    spread_cost_profit = await run_mt5_task(mt5.order_calc_profit, mt5.ORDER_TYPE_BUY, symbol, volume, tick.ask, tick.bid)
    if spread_cost_profit is not None:
        spread_cost_usd = abs(spread_cost_profit)
    else:
        spread_cost_usd = spread_raw * contract_size * volume
        
    logger.info(f"{'Current Spread (Points)':<25}: {spread_points}")
    logger.info(f"{'Current Spread (Price)':<25}: {spread_raw:.3f}")
    logger.info(f"{'Swap Long':<25}: {swap_long}")
    logger.info(f"{'Swap Short':<25}: {swap_short}")
    logger.info(f"{'Spread Friction Cost':<25}: ${spread_cost_usd:.4f}")
    
    # Fetch M15 rates for ATR (fetching 15 bars for a 14-period ATR ensures first TR is valid)
    rates = await run_mt5_task(mt5.copy_rates_from_pos, symbol, mt5.TIMEFRAME_M15, 0, 15)
    if rates is None or len(rates) == 0:
        logger.error("Could not fetch M15 rates to calculate ATR.")
        return
        
    atr = calculate_atr(rates, 14)
    
    # Calculate expected ATR target in USD
    atr_profit = await run_mt5_task(mt5.order_calc_profit, mt5.ORDER_TYPE_BUY, symbol, volume, tick.ask, tick.ask + atr)
    if atr_profit is not None:
        atr_usd = atr_profit
    else:
        atr_usd = atr * contract_size * volume
        
    logger.info(f"{'M15 ATR (14)':<25}: {atr:.3f}")
    logger.info(f"{'M15 ATR Target (USD)':<25}: ${atr_usd:.4f}")
    
    if atr_usd <= 0:
        logger.error("ATR in USD is zero or negative.")
        return
        
    friction_pct = (spread_cost_usd / atr_usd) * 100.0
    logger.info(f"{'Friction / ATR Target %':<25}: {friction_pct:.2f} %")
    
    if friction_pct > 15.0:
        logger.warning(f"{'Status':<25}: WARNING (Friction > 15%. Liquidity toxic for scalping!)")
    else:
        logger.info(f"{'Status':<25}: PASSED (<= 15% of ATR target)")
    logger.info("-" * 60)

async def main():
    logger.info("=" * 60)
    logger.info(f"{'PRE-FLIGHT DIAGNOSTIC REPORT':^60}")
    logger.info("=" * 60)
    
    if not await init_mt5():
        return
        
    symbol = "XAUUSD"
    # Ensure symbol is visible in market watch
    await run_mt5_task(mt5.symbol_select, symbol, True)
    
    try:
        await task1_latency_auditor(symbol)
        await task2_margin_stress_test(symbol)
        await task3_spread_friction_analysis(symbol)
    except Exception as e:
        logger.error(f"An error occurred during diagnostics: {e}", exc_info=True)
    finally:
        await shutdown_mt5()
        logger.info("Diagnostics complete.")

if __name__ == "__main__":
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
