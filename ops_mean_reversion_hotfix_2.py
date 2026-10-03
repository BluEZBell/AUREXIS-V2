import os

def apply_mean_reversion_patch_2_3():
    file_path = 'src/strategy/alpha_harvester.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target2 = '''            if len(active_cycles) == 0 and self.auto_sniper:
                if await self.check_whipsaw_lock(ind):
                    return'''
    replace2 = '''            if len(active_cycles) == 0 and self.auto_sniper:
                adx_m15 = ind.get('adx_m15', 20.0)
                if await self.check_whipsaw_lock(ind) and adx_m15 >= 22.0:
                    return'''
    
    if target2 in content:
        content = content.replace(target2, replace2)
        print("? Part 2 applied: Unblocking sideways regime.")
    else:
        print("?? Part 2 skipped: target not found.")

    target3 = '''acc_info = await run_mt5_task(mt5.account_info)
                    current_equity = acc_info.equity if acc_info else 100.0
                    dynamic_vol = self.risk_manager.calculate_lot_size(current_equity, atr=ind.get('atr_m15', 200.0))
                    sig = SignalEvent(event.symbol, direction, self.strategy_id, event.bid, conviction=conv, volume=dynamic_vol, cycle_id=cycle_id, order_type="PROBE")'''
                      
    replace3 = '''acc_info = await run_mt5_task(mt5.account_info)
                    current_equity = acc_info.equity if acc_info else 100.0
                    dynamic_vol = self.risk_manager.calculate_lot_size(current_equity, atr=ind.get('atr_m15', 200.0))
                    adx_m15 = ind.get('adx_m15', 20.0)
                    order_type = "MEAN_REV" if adx_m15 < 22.0 else "PROBE"
                    sig = SignalEvent(event.symbol, direction, self.strategy_id, event.bid, conviction=conv, volume=dynamic_vol, cycle_id=cycle_id, order_type=order_type)'''
    
    if target3 in content:
        content = content.replace(target3, replace3)
        print("? Part 3 applied: Tagging SignalEvent with order_type.")
    else:
        print("?? Part 3 skipped: target not found.")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    apply_mean_reversion_patch_2_3()
