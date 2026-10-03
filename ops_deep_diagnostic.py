"""
AUREXIS V2 Deep Forensic Diagnostic
Phase 11: Forensic Entry Analysis
Extracts historical MT5 deals and recalculates indicator states at the exact microsecond of execution.
"""

import MetaTrader5 as mt5
import numpy as np
import sys
from datetime import datetime, timezone
import time
from src.core import config
from src.core.math_engine import calc_ema, calc_rsi, calc_bollinger_bands

def run_diagnostics():
    if not mt5.initialize(path=config.MT5_TERMINAL_PATH):
        print(f"[FAIL] MT5 Initialization failed: {mt5.last_error()}")
        sys.exit(1)

    print("=" * 115)
    print(" AUREXIS FORENSIC DIAGNOSTIC | DEEP INDICATOR AUDIT")
    print("=" * 115)

    symbol = config.TRADING_SYMBOL
    
    # Get today's deals
    now = datetime.now()
    midnight = datetime(now.year, now.month, now.day)
    
    deals = mt5.history_deals_get(midnight, now, group=f"*{symbol}*")
    
    if deals is None:
        print(f"[!] No deals found for {symbol} today or failed to retrieve: {mt5.last_error()}")
        mt5.shutdown()
        sys.exit(0)
        
    # Filter for ENTRY deals
    entry_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_IN]
    
    if not entry_deals:
        print("[i] No ENTRY deals found for today.")
        mt5.shutdown()
        sys.exit(0)
        
    # Take last 15
    recent_deals = entry_deals[-15:]
    
    print(f"{'Ticket':<10} | {'Type':<5} | {'Entry':<8} | {'EMA20':<8} | {'BB_Low':<8} | {'BB_Up':<8} | {'RSI':<6} | {'PnL':<6} | {'Verdict'}")
    print("-" * 115)
    
    for deal in recent_deals:
        deal_type = "BUY" if deal.type == mt5.ORDER_TYPE_BUY else "SELL" if deal.type == mt5.ORDER_TYPE_SELL else "UNKNOWN"
        if deal_type == "UNKNOWN":
            continue
            
        deal_time = deal.time
        
        # Fetch 50 M5 candles ending exactly at deal_time
        # mt5.copy_rates_from gets bars up to the specific time
        rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_M5, deal_time, 50)
        
        if rates is None or len(rates) < 50:
            print(f"{deal.ticket:<10} | {deal_type:<5} | {deal.price:<8.2f} | [Error fetching historical rates]")
            continue
            
        closes = np.array([r['close'] for r in rates])
        
        ema20 = calc_ema(closes, 20)[-1]
        bb_up, _, bb_low = calc_bollinger_bands(closes, 20, 2.0)
        bb_upper_val = bb_up[-1]
        bb_lower_val = bb_low[-1]
        rsi = calc_rsi(closes, 14)[-1]
        
        price = deal.price
        pnl = deal.profit
        
        verdict = "[UNKNOWN/FAILED GATING]"
        if deal_type == "BUY":
            if price > ema20 and rsi > 60:
                verdict = "[CRITICAL FAULT: BOUGHT THE TOP]"
            elif price <= bb_lower_val + (bb_upper_val - bb_lower_val)*0.1 and rsi < 45:
                verdict = "[RANGE PROBE OK]"
            elif 35 <= rsi <= 58 and ema20 * 0.9990 <= price <= ema20 * 1.0005:
                verdict = "[TREND PULLBACK OK]"
        else:
            if price < ema20 and rsi < 40:
                verdict = "[CRITICAL FAULT: SOLD THE BOTTOM]"
            elif price >= bb_upper_val - (bb_upper_val - bb_lower_val)*0.1 and rsi > 55:
                verdict = "[RANGE PROBE OK]"
            elif 42 <= rsi <= 65 and ema20 * 0.9995 <= price <= ema20 * 1.0010:
                verdict = "[TREND RIP OK]"
                
        print(f"{deal.ticket:<10} | {deal_type:<5} | {price:<8.2f} | {ema20:<8.2f} | {bb_lower_val:<8.2f} | {bb_upper_val:<8.2f} | {rsi:<6.1f} | {pnl:<6.2f} | {verdict}")

    print("=" * 115)
    mt5.shutdown()

if __name__ == "__main__":
    run_diagnostics()
