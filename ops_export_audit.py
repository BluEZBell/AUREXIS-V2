import MetaTrader5 as mt5
import sys
from datetime import datetime
import src.core.config as config
import os

def main():
    if not mt5.initialize(path=config.MT5_TERMINAL_PATH):
        sys.exit(1)
        
    to_date = datetime.now()
    from_date = datetime(2026, 9, 30, 3, 57, 5)
    symbol = config.TRADING_SYMBOL
    deals = mt5.history_deals_get(from_date, to_date, group=f"*{symbol}*")
    
    if not deals:
        mt5.shutdown()
        sys.exit(0)
        
    positions = {}
    for d in deals:
        if d.type == mt5.DEAL_TYPE_BALANCE:
            continue
            
        pos_id = d.position_id
        if pos_id not in positions:
            positions[pos_id] = {
                'open_time': None,
                'close_time': None,
                'type': None,
                'volume': 0.0,
                'open_price': 0.0,
                'close_price': 0.0,
                'profit': 0.0,
                'commission': 0.0,
                'swap': 0.0,
                'status': 'OPEN'
            }
            
        p = positions[pos_id]
        if d.entry == mt5.DEAL_ENTRY_IN:
            p['open_time'] = d.time
            p['type'] = "BUY" if d.type == mt5.DEAL_TYPE_BUY else "SELL"
            p['volume'] = d.volume
            p['open_price'] = d.price
            p['commission'] += d.commission
            p['swap'] += d.swap
            p['profit'] += d.profit
        elif d.entry in (mt5.DEAL_ENTRY_OUT, mt5.DEAL_ENTRY_OUT_BY, mt5.DEAL_ENTRY_INOUT):
            p['close_time'] = d.time
            p['close_price'] = d.price
            p['commission'] += d.commission
            p['swap'] += d.swap
            p['profit'] += d.profit
            p['status'] = 'CLOSED'
            
    valid_positions = [(pid, p) for pid, p in positions.items() if p['open_time'] is not None]
    valid_positions.sort(key=lambda x: x[1]['open_time'])
    
    out_lines = []
    out_lines.append("===================================================================================================================================================")
    out_lines.append(f"{'POS ID':<12} | {'TYPE':<5} | {'VOL':<5} | {'OPEN TIME (UTC)':<20} | {'CLOSE TIME (UTC)':<20} | {'HOLD TIME':<10} | {'OPEN P.':<9} | {'CLOSE P.':<9} | {'NET PNL':<10}")
    out_lines.append("---------------------------------------------------------------------------------------------------------------------------------------------------")
    
    total_trades = 0
    gross_profit = 0.0
    total_commission = 0.0
    total_swap = 0.0
    
    def format_duration(seconds):
        if seconds < 60: return f"{int(seconds)}s"
        elif seconds < 3600: return f"{int(seconds)//60}m {int(seconds)%60}s"
        else: return f"{int(seconds)//3600}h {(int(seconds)%3600)//60}m"
            
    for pos_id, p in valid_positions:
        open_time_str = datetime.fromtimestamp(p['open_time']).strftime('%Y-%m-%d %H:%M:%S')
        if p['close_time']:
            close_time_str = datetime.fromtimestamp(p['close_time']).strftime('%Y-%m-%d %H:%M:%S')
            duration = p['close_time'] - p['open_time']
            duration_str = format_duration(duration)
        else:
            close_time_str = "STILL OPEN"
            duration = (datetime.now().timestamp() - p['open_time'])
            duration_str = format_duration(duration) + "*"
            
        net_pnl = p['profit'] + p['commission'] + p['swap']
        gross_profit += p['profit']
        total_commission += p['commission']
        total_swap += p['swap']
        total_trades += 1
        
        out_lines.append(f"{pos_id:<12} | {p['type']:<5} | {p['volume']:<5.2f} | {open_time_str:<20} | {close_time_str:<20} | {duration_str:<10} | {p['open_price']:<9.2f} | {p['close_price']:<9.2f} | {net_pnl:<10.2f}")
        
    out_lines.append("===================================================================================================================================================")
    out_lines.append(" IN-DEPTH TRADE FORENSICS (Aggregated by Position)")
    out_lines.append(f" Total Trades Executed : {total_trades}")
    out_lines.append(f" Gross Profit          : $ {gross_profit:.2f}")
    out_lines.append(f" Total Commission      : $ {total_commission:.2f}")
    out_lines.append(f" Total Swap            : $ {total_swap:.2f}")
    out_lines.append(f" ------------------------------------")
    total_net = gross_profit + total_commission + total_swap
    out_lines.append(f" Net Realized PnL      : $ {total_net:.2f}")
    out_lines.append("===================================================================================================================================================")
    
    filepath = r'C:\Users\bluzp\.gemini\antigravity\brain\241c23b7-6545-4835-9bd1-d145fc33b30c\Execution_Audit_Full.md'
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('# Full Execution Audit (After 2026-09-30 03:57:05)\n\n`	ext\n')
        f.write('\n'.join(out_lines))
        f.write('\n`\n')
        
    mt5.shutdown()

if __name__ == '__main__':
    main()
