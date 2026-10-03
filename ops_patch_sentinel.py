import os

def patch_sentinel():
    file_path = 'src/execution/sentinel.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update __init__
    init_target = '''        self.profit_floors: Dict[int, float] = {}
        self._running = False'''
        
    init_replace = '''        self.profit_floors: Dict[int, float] = {}
        self._last_logged_floor: Dict[int, float] = {}
        self._running = False'''
        
    if init_target in content:
        content = content.replace(init_target, init_replace)
        print("? Added _last_logged_floor to __init__")

    # 2. Update process_tick cleanup
    cleanup_target = '''        if not positions:
            self.mfe_vault.clear()
            self.profit_floors.clear()
            self.closing_tickets.clear()
            return'''
            
    cleanup_replace = '''        if not positions:
            self.mfe_vault.clear()
            self.profit_floors.clear()
            self._last_logged_floor.clear()
            self.closing_tickets.clear()
            return'''
            
    if cleanup_target in content:
        content = content.replace(cleanup_target, cleanup_replace)
        print("? Added _last_logged_floor.clear()")

    # 3. Update logging logic
    log_target = '''            current_floor = self.profit_floors.get(ticket)
            if floor is not None and (current_floor is None or floor > current_floor):
                self.profit_floors[ticket] = floor
                logger.info(f"MFE Vault: Locking profit floor at $ for Ticket {ticket}")'''
                
    log_replace = '''            current_floor = self.profit_floors.get(ticket)
            if floor is not None and (current_floor is None or floor > current_floor):
                self.profit_floors[ticket] = floor
                
                last_logged = self._last_logged_floor.get(ticket, -999.0)
                # Require at least 0.10 difference to prevent micro-spread flutter spam
                if floor >= last_logged + 0.10:
                    logger.info(f"MFE Vault: Locking profit floor at  for Ticket {ticket}")
                    self._last_logged_floor[ticket] = floor'''
                    
    if log_target in content:
        content = content.replace(log_target, log_replace)
        print("? Updated MFE Vault logging logic")

    # 4. Update close reason log
    close_log_target = '''            if close_reason:
                logger.warning(f"Tick Sentinel: Executing CLOSE for Ticket {ticket}. Reason: {close_reason}. Profit: $")'''
                
    close_log_replace = '''            if close_reason:
                logger.warning(f"Tick Sentinel: Executing CLOSE for Ticket {ticket}. Reason: {close_reason}. Profit: ")'''
                
    if close_log_target in content:
        content = content.replace(close_log_target, close_log_replace)
        print("? Updated close reason log to include PnL")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    patch_sentinel()
