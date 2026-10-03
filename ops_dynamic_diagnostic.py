import sys
import numpy as np
import MetaTrader5 as mt5
import src.core.config as config
from src.core.dynamic_params import DynamicParamStore

def run_diagnostic():
    print("Initializing MT5 Connection...")
    if not mt5.initialize(path=config.MT5_TERMINAL_PATH):
        print(f"Failed to initialize MT5, error code: {mt5.last_error()}")
        sys.exit(1)

    symbol = config.TRADING_SYMBOL
    print(f"Connected. Fetching data for {symbol}...")

    sym_info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)

    if not sym_info or not tick:
        print(f"Failed to get symbol info or tick for {symbol}")
        mt5.shutdown()
        sys.exit(1)

    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 15)
    if rates is None or len(rates) < 15:
        print(f"Failed to fetch sufficient M15 rates for {symbol}")
        mt5.shutdown()
        sys.exit(1)

    true_ranges = []
    for i in range(1, len(rates)):
        high = rates[i]['high']
        low = rates[i]['low']
        prev_close = rates[i-1]['close']
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
    
    atr_m15 = np.mean(true_ranges)
    atr_points = atr_m15 / sym_info.point

    param_store = DynamicParamStore()
    
    spread_points = (tick.ask - tick.bid) / sym_info.point
    spread_in_ticks = (tick.ask - tick.bid) / sym_info.trade_tick_size
    
    test_volume = 0.10
    spread_cost_usd = spread_in_ticks * sym_info.trade_tick_value * test_volume
    spread_cost_usd = max(spread_cost_usd, 0.50 * (test_volume / 0.10))

    activation_tier_0 = spread_cost_usd * 2.0
    activation_tier_1 = spread_cost_usd * 4.0
    activation_tier_2 = spread_cost_usd * 10.0

    sl_min, sl_max = param_store.get_sl_bounds(atr_points)

    print("\n" + "="*80)
    print(" AUREXIS V2 : REAL-TIME DYNAMIC PARAMETER DIAGNOSTIC (X-RAY)")
    print("="*80)
    print(f" Symbol             : {symbol}")
    print(f" Bid / Ask          : {tick.bid:.5f} / {tick.ask:.5f}")
    print(f" Current Spread     : {spread_points:.1f} points")
    print(f" Spread Cost (0.10) : $ {spread_cost_usd:.2f}")
    print("-" * 80)
    print(f" Current Volatility : {atr_points:.1f} points (ATR M15)")
    print(f" Dynamic SL Bounds  : Min {sl_min:.1f} points | Max {sl_max:.1f} points")
    print("-" * 80)
    print(" DYNAMIC MFE VAULT (COST-BASIS TIERS)")
    print(f" [Tier 0] Micro-Defense (x2) : $ {activation_tier_0:.2f}  => Locks fractional spread to ensure green")
    print(f" [Tier 1] Break-Even    (x4) : $ {activation_tier_1:.2f}  => Locks spread * 1.5")
    print(f" [Tier 2] Free-Roll    (x10) : $ {activation_tier_2:.2f}  => Activates 50% Trailing")
    print("="*80 + "\n")

    mt5.shutdown()

if __name__ == '__main__':
    run_diagnostic()
