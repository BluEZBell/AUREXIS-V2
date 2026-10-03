import os

def hotfix_unlimited_apex():
    file_path = 'src/execution/risk_manager.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Inject import time if not present
    if "import time" not in content:
        content = "import time\n" + content

    target = '''            if max_profit_achieved_pct >= trailing_lock_trigger:
                floor_equity = self.highest_equity - (start_equity * (trailing_floor_buffer / 100.0))
                if current_equity < floor_equity:
                    logger.critical("UNLIMITED_APEX: Trailing Profit Floor Hit! (HALT DISABLED for Antigravity)")'''
                    
    replace = '''            if max_profit_achieved_pct >= trailing_lock_trigger:
                floor_equity = self.highest_equity - (start_equity * (trailing_floor_buffer / 100.0))
                if current_equity < floor_equity:
                    current_time = time.time()
                    if not hasattr(self, '_last_trail_update'):
                        self._last_trail_update = {}
                    if current_time - self._last_trail_update.get("ACCOUNT", 0.0) > 10.0:
                        logger.critical("UNLIMITED_APEX: Trailing Profit Floor Hit! (HALT DISABLED for Antigravity)")
                        self._last_trail_update["ACCOUNT"] = current_time'''

    if target in content:
        content = content.replace(target, replace)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? Hotfix applied to risk_manager.py")
    else:
        print("?? Target string not found in risk_manager.py")

if __name__ == '__main__':
    hotfix_unlimited_apex()
