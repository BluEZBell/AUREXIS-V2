import os

def apply_micro_kill():
    file_path = 'src/execution/sentinel.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''            close_reason = None
            acc_info = await run_mt5_task(lambda: mt5.account_info())
            equity = getattr(acc_info, 'equity', 100.0) if acc_info else 100.0
            emergency_sl = equity * -0.15
            
            if current_profit <= emergency_sl:'''
            
    replace = '''            close_reason = None
            acc_info = await run_mt5_task(lambda: mt5.account_info())
            equity = getattr(acc_info, 'equity', 100.0) if acc_info else 100.0
            emergency_sl = equity * -0.15
            
            pos_dir = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
            if self._latest_m15_trend:
                if pos_dir == "BUY" and self._latest_m15_trend == "BEARISH":
                    close_reason = "STRUCTURAL_KILL_BEARISH"
                elif pos_dir == "SELL" and self._latest_m15_trend == "BULLISH":
                    close_reason = "STRUCTURAL_KILL_BULLISH"
            
            if not close_reason and current_profit <= emergency_sl:'''

    if target in content:
        content = content.replace(target, replace)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? Patch applied successfully: Micro-Structural Kill.")
    else:
        print("?? Patch skipped: Target string not found.")

if __name__ == '__main__':
    apply_micro_kill()
