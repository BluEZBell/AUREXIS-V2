import os

def apply_bridge_patch():
    file_path = 'src/execution/bridge.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        if 'spacing = self.param_store.get_grid_spacing(' in line and '* point' in line:
            new_lines.append('                acc_info = await run_mt5_task(mt5.account_info)')
            new_lines.append('                eq = acc_info.equity if acc_info else 1000.0')
            new_lines.append('                spacing = self.param_store.get_grid_spacing(self._latest_m15_atr, getattr(signal, "conviction", 50.0), config.TRADING_SYMBOL, eq) * point')
            print("? Line replaced!")
        else:
            new_lines.append(line)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

if __name__ == '__main__':
    apply_bridge_patch()
