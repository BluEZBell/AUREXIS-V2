import os

def hotfix_dynamic_lot():
    file_path = 'src/strategy/alpha_harvester.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '                    sig = SignalEvent(event.symbol, direction, self.strategy_id, event.bid, conviction=conv, volume=0.10, cycle_id=cycle_id, order_type="PROBE")'
    
    replacement = '''                    acc_info = await run_mt5_task(mt5.account_info)
                    current_equity = acc_info.equity if acc_info else 100.0
                    dynamic_vol = self.risk_manager.calculate_lot_size(current_equity, atr=ind.get('atr_m15', 200.0))
                    sig = SignalEvent(event.symbol, direction, self.strategy_id, event.bid, conviction=conv, volume=dynamic_vol, cycle_id=cycle_id, order_type="PROBE")'''

    if target in content:
        content = content.replace(target, replacement)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? Patch applied successfully: Removed hardcoded 0.10 volume for dynamic lot sizing.")
    else:
        print("?? Patch skipped: Target string not found.")

if __name__ == '__main__':
    hotfix_dynamic_lot()
