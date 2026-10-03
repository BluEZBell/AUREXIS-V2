import sys
from datetime import datetime, timedelta, time
import MetaTrader5 as mt5
import src.core.config as config

def calculate_eod_report():
    print("Initializing MT5 Connection...")
    if not mt5.initialize(path=config.MT5_TERMINAL_PATH):
        print(f"Failed to initialize MT5, error code: {mt5.last_error()}")
        sys.exit(1)

    print("Connected. Fetching EOD Reconciliation Data...")
    
    # Define current calendar day (Broker time approx local time or UTC based on mt5 settings, 
    # but using current datetime as reference)
    now = datetime.now()
    start_of_day = datetime.combine(now.date(), time(0, 0, 0))
    end_of_day = datetime.combine(now.date(), time(23, 59, 59))

    deals = mt5.history_deals_get(start_of_day, end_of_day)
    
    if deals is None:
        print(f"Failed to fetch history deals, error code: {mt5.last_error()}")
        mt5.shutdown()
        sys.exit(1)

    total_trades = 0
    winning_trades = 0
    gross_profit = 0.0
    gross_loss = 0.0
    total_commission = 0.0
    total_swap = 0.0
    net_pnl = 0.0

    current_balance = 0.0
    peak_balance = 0.0
    max_drawdown = 0.0

    # Sort deals by time to calculate drawdown over the sequence
    deals = sorted(deals, key=lambda d: d.time)

    for deal in deals:
        # Only process deals that affect PnL (Deal Entry In/Out or Deal Out)
        # deal.type == 0 is DEAL_TYPE_BUY, 1 is DEAL_TYPE_SELL
        # deal.entry == 1 is DEAL_ENTRY_OUT (Close position)
        if deal.entry == 1 or deal.entry == 2: # DEAL_ENTRY_OUT or DEAL_ENTRY_INOUT
            total_trades += 1
            pnl = deal.profit
            total_commission += deal.commission
            total_swap += deal.swap
            deal_net = pnl + deal.commission + deal.swap
            
            net_pnl += deal_net
            
            if pnl > 0:
                winning_trades += 1
                gross_profit += pnl
            else:
                gross_loss += abs(pnl)
                
            current_balance += deal_net
            if current_balance > peak_balance:
                peak_balance = current_balance
            
            drawdown = peak_balance - current_balance
            if drawdown > max_drawdown:
                max_drawdown = drawdown

    win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

    print("\n" + "="*80)
    print(f" AUREXIS V2 : END-OF-DAY RECONCILIATION REPORT")
    print(f" Date: {start_of_day.strftime('%Y-%m-%d')} | Timeframe: 00:00:00 - 23:59:59")
    print("="*80)
    print(" [ EXECUTION METRICS ]")
    print(f" Total Trades Executed : {total_trades}")
    print(f" Win Rate              : {win_rate:.2f}% ({winning_trades} / {total_trades})")
    print(f" Profit Factor         : {profit_factor:.2f}")
    print(f" Max Daily Drawdown    : $ {max_drawdown:.2f}")
    print("-" * 80)
    print(" [ FINANCIAL SUMMARY ]")
    print(f" Gross Profit          : $ {gross_profit:.2f}")
    print(f" Gross Loss            : $ -{gross_loss:.2f}")
    print(f" Total Commission      : $ {total_commission:.2f}")
    print(f" Total Swap            : $ {total_swap:.2f}")
    print("-" * 80)
    print(f" NET REALIZED PNL      : $ {net_pnl:.2f}")
    print("="*80 + "\n")

    mt5.shutdown()

if __name__ == '__main__':
    calculate_eod_report()
