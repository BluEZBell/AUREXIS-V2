import sys
from datetime import datetime
import MetaTrader5 as mt5
import src.core.config as config

def run_audit():
    if not mt5.initialize(path=config.MT5_TERMINAL_PATH):
        print("Failed to initialize MT5")
        sys.exit(1)
        
    from_date = datetime(2026, 9, 30, 3, 57, 5)
    to_date = datetime.now()
    
    deals = mt5.history_deals_get(from_date, to_date, group=f"*{config.TRADING_SYMBOL}*")
    
    if not deals:
        print("No deals found in the specified time range.")
        mt5.shutdown()
        sys.exit(0)
        
    positions = {}
    for d in deals:
        if d.type in [mt5.DEAL_TYPE_BALANCE, mt5.DEAL_TYPE_CREDIT]:
            continue
            
        pos_id = d.position_id
        if pos_id not in positions:
            positions[pos_id] = {
                'id': pos_id,
                'type': 'BUY' if d.type == mt5.DEAL_TYPE_BUY else 'SELL',
                'volume': 0.0,
                'open_time': None,
                'close_time': None,
                'open_price': 0.0,
                'close_price': 0.0,
                'profit': 0.0,
                'commission': 0.0,
                'swap': 0.0
            }
            
        pos = positions[pos_id]
        pos['commission'] += d.commission
        pos['swap'] += d.swap
        pos['profit'] += d.profit
        
        if d.entry == mt5.DEAL_ENTRY_IN:
            pos['open_time'] = datetime.fromtimestamp(d.time)
            pos['open_price'] = d.price
            pos['volume'] = d.volume
            pos['type'] = 'BUY' if d.type == mt5.DEAL_TYPE_BUY else 'SELL'
        elif d.entry in [mt5.DEAL_ENTRY_OUT, mt5.DEAL_ENTRY_INOUT]:
            pos['close_time'] = datetime.fromtimestamp(d.time)
            pos['close_price'] = d.price

    print("="*131)
    print(f"{'POS ID':<12} | {'TYPE':<5} | {'VOL':<5} | {'OPEN TIME (UTC)':<20} | {'CLOSE TIME (UTC)':<20} | {'HOLD TIME':<10} | {'OPEN P.':<9} | {'CLOSE P.':<9} | {'NET PNL':<9}")
    print("-" * 131)
    
    sorted_pos = sorted(positions.values(), key=lambda x: x['open_time'] if x['open_time'] else datetime.max)
    
    total_trades = 0
    gross_profit = 0.0
    total_comm = 0.0
    total_swap = 0.0
    
    for pos in sorted_pos:
        if pos['open_time'] is None:
            continue
            
        close_time_str = pos['close_time'].strftime('%Y-%m-%d %H:%M:%S') if pos['close_time'] else "STILL OPEN"
        
        hold_time_str = "N/A"
        if pos['close_time']:
            delta = int((pos['close_time'] - pos['open_time']).total_seconds())
            mins, secs = divmod(delta, 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                hold_time_str = f"{hours}h {mins}m"
            elif mins > 0:
                hold_time_str = f"{mins}m {secs}s"
            else:
                hold_time_str = f"{secs}s"
        else:
            delta = int((datetime.now() - pos['open_time']).total_seconds())
            mins, secs = divmod(delta, 60)
            hold_time_str = f"{mins}m {secs}s*"

        net_pnl = pos['profit'] + pos['commission'] + pos['swap']
        
        total_trades += 1
        gross_profit += pos['profit']
        total_comm += pos['commission']
        total_swap += pos['swap']
        
        print(f"{pos['id']:<12} | {pos['type']:<5} | {pos['volume']:<5.2f} | {pos['open_time'].strftime('%Y-%m-%d %H:%M:%S'):<20} | {close_time_str:<20} | {hold_time_str:<10} | {pos['open_price']:<9.2f} | {pos['close_price']:<9.2f} | {net_pnl:<9.2f}")

    net_realized = gross_profit + total_comm + total_swap
    
    print("="*131)
    print(" IN-DEPTH TRADE FORENSICS (Aggregated by Position)")
    print(f" Total Trades Executed : {total_trades}")
    print(f" Gross Profit          : $ {gross_profit:.2f}")
    print(f" Total Commission      : $ {total_comm:.2f}")
    print(f" Total Swap            : $ {total_swap:.2f}")
    print("-" * 36)
    print(f" Net Realized PnL      : $ {net_realized:.2f}")
    print("="*131)
    
    mt5.shutdown()

if __name__ == '__main__':
    run_audit()
