import os

def apply_phase5():
    # 1. Update config.py
    cfg_path = 'src/core/config.py'
    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg = f.read()
        
    if "MT5_LOGIN =" not in cfg:
        cfg += '''\n
# --- PHASE 5: Secure Execution & Dry Run ---
MT5_LOGIN = os.getenv("MT5_LOGIN", "")
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() in ["true", "1", "yes"]
'''
        with open(cfg_path, 'w', encoding='utf-8') as f:
            f.write(cfg)
        print("? Added Phase 5 env vars to config.py")
        
    # Create .env.example
    env_example = '''MAGIC_NUMBER=777999
TRADING_SYMBOL=GOLD
PROFILE_MODE=UNLIMITED_APEX
MAX_DAILY_LOSS_PCT=6.5
MAX_OPEN_POSITIONS=9999
WEB_PORT=8000
MT5_TERMINAL_PATH=C:\Program Files\MetaTrader 5\terminal64.exe

# Phase 5: Secure Execution
MT5_LOGIN=12345678
MT5_PASSWORD=YourPasswordHere
MT5_SERVER=YourBroker-Demo
DRY_RUN=True
'''
    with open('.env.example', 'w', encoding='utf-8') as f:
        f.write(env_example)
    print("? Created .env.example")
    
    # 2. Update bridge.py initialize()
    bridge_path = 'src/execution/bridge.py'
    with open(bridge_path, 'r', encoding='utf-8') as f:
        br_content = f.read()
        
    init_target = '''    async def initialize(self):
        def _init_mt5():
            return mt5.initialize(path=self.terminal_path)
            
        success = await run_mt5_task(_init_mt5)'''
        
    init_replace = '''    async def initialize(self):
        def _init_mt5():
            if mt5.initialize(path=self.terminal_path):
                if config.MT5_LOGIN and config.MT5_PASSWORD and config.MT5_SERVER:
                    login_acc = int(config.MT5_LOGIN)
                    if not mt5.login(login_acc, password=config.MT5_PASSWORD, server=config.MT5_SERVER):
                        logger.error(f"MT5 login failed. Error: {mt5.last_error()}")
                        return False
                    logger.info(f"MT5 Login successful on account {login_acc}")
                return True
            return False
            
        success = await run_mt5_task(_init_mt5)'''
        
    if init_target in br_content:
        br_content = br_content.replace(init_target, init_replace)
        print("? Updated bridge initialize() for secure login")
        
    # 3. Update bridge process_signal for DRY_RUN
    order_send_target = '''            for attempt in range(3):
                result = await asyncio.to_thread(mt5.order_send, req)'''
                
    order_send_replace = '''            for attempt in range(3):
                if getattr(config, 'DRY_RUN', False):
                    import random
                    class MockResult:
                        def __init__(self):
                            self.order = random.randint(1000000, 9999999)
                            self.retcode = mt5.TRADE_RETCODE_DONE
                    logger.warning(f"DRY RUN: Bypassing order_send. Mocking success for req: {req}")
                    result = MockResult()
                else:
                    result = await asyncio.to_thread(mt5.order_send, req)'''
                    
    if order_send_target in br_content:
        br_content = br_content.replace(order_send_target, order_send_replace)
        print("? Added DRY_RUN to process_signal")
        
    close_target = '''            return mt5.order_send(request)
            
        result = None
        for attempt in range(3):
            result = await run_mt5_task(_close)'''
            
    close_replace = '''            if getattr(config, 'DRY_RUN', False):
                import random
                class MockResult:
                    def __init__(self):
                        self.order = request['position']
                        self.retcode = mt5.TRADE_RETCODE_DONE
                logger.warning(f"DRY RUN: Bypassing close order. Mocking success for req: {request}")
                return MockResult()
            return mt5.order_send(request)
            
        result = None
        for attempt in range(3):
            result = await run_mt5_task(_close)'''
            
    if close_target in br_content:
        br_content = br_content.replace(close_target, close_replace)
        print("? Added DRY_RUN to close_position")

    mod_target = '''            return mt5.order_send(request)
        result = await run_mt5_task(_mod)'''
        
    mod_replace = '''            if getattr(config, 'DRY_RUN', False):
                class MockResult:
                    def __init__(self):
                        self.retcode = mt5.TRADE_RETCODE_DONE
                logger.warning(f"DRY RUN: Bypassing SL modify. Mocking success for req: {request}")
                return MockResult()
            return mt5.order_send(request)
        result = await run_mt5_task(_mod)'''
        
    if mod_target in br_content:
        br_content = br_content.replace(mod_target, mod_replace)
        print("? Added DRY_RUN to modify_sl")

    with open(bridge_path, 'w', encoding='utf-8') as f:
        f.write(br_content)

if __name__ == '__main__':
    apply_phase5()
