import re
import sys
import os

with open('src/execution/risk_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

imports = "import os\nimport json\nimport asyncio\n"
content = content.replace("import time\nimport datetime\n", imports + "import time\nimport datetime\n")

hwm_logic = """
HWM_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "aurexis_hwm.json")
LOCK_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "DOOMSDAY.lock")
"""
content = content.replace("class RiskManager:", hwm_logic + "\nclass RiskManager:")

init_logic = """        self.halted = False
        
        # Phase 21: High-Water Mark Tracker
        self._hwm = config.INITIAL_ACCOUNT_BALANCE
        self._doomsday_locked = False
        self._load_hwm_sync()

    def _load_hwm_sync(self):
        if os.path.exists(LOCK_FILE):
            self._doomsday_locked = True
            logger.critical("RiskManager: DOOMSDAY.lock exists! Global Drawdown breach is permanent until manually lifted.")
            self.halted = True
            
        if os.path.exists(HWM_FILE):
            try:
                with open(HWM_FILE, 'r') as f:
                    data = json.load(f)
                    self._hwm = data.get("hwm", config.INITIAL_ACCOUNT_BALANCE)
            except Exception as e:
                logger.error(f"Failed to load HWM: {e}")
        
        logger.info(f"RiskManager initialized. Current HWM: {self._hwm:.2f}. Initial Balance: {config.INITIAL_ACCOUNT_BALANCE:.2f}. Max Overall DD: {config.MAX_OVERALL_DRAWDOWN_PCT}% (Type: {config.DRAWDOWN_TYPE}).")

    async def _save_hwm(self):
        def _write():
            with open(HWM_FILE, 'w') as f:
                json.dump({"hwm": self._hwm}, f)
        await asyncio.to_thread(_write)
        
    async def _trigger_doomsday(self, msg: str):
        self._doomsday_locked = True
        self.halted = True
        logger.critical(f"DOOMSDAY LOCKDOWN: {msg}")
        
        def _write_lock():
            with open(LOCK_FILE, 'w') as f:
                f.write(msg)
        await asyncio.to_thread(_write_lock)
        
        from src.core.event_bus import SentinelKillEvent, RiskAlertEvent, CommandEvent, ErrorEvent
        await self.event_bus.publish(RiskAlertEvent(level="CRITICAL", message=msg))
        await self.event_bus.publish(ErrorEvent(message="GLOBAL DRAWDOWN LIMIT REACHED - PANIC", critical=True))
        await self.event_bus.publish(CommandEvent(action="PANIC_HALT"))
        await self.event_bus.publish(SentinelKillEvent(ticket=0, cycle_id=0, reason="DOOMSDAY_DRAWDOWN", pnl=0.0))
"""
content = content.replace("        self.halted = False", init_logic)

check_logic = """    async def check_drawdown_limits(self, current_equity: float, start_equity: float) -> bool:
        if self._doomsday_locked:
            return False
            
        if self.halted:
            return False
            
        try:
            current_equity = float(current_equity)
            start_equity = float(start_equity)
        except (TypeError, ValueError):
            return True
            
        if start_equity <= 0:
            return True

        # Phase 21: High-Water Mark Tracking
        if current_equity > self._hwm:
            self._hwm = current_equity
            asyncio.create_task(self._save_hwm())
            
        if config.DRAWDOWN_TYPE == "EQUITY_TRAILING":
            ref_balance = self._hwm
        else:
            ref_balance = config.INITIAL_ACCOUNT_BALANCE
            
        global_drawdown_pct = ((ref_balance - current_equity) / ref_balance) * 100.0 if ref_balance > 0 else 0.0
        
        if global_drawdown_pct >= config.MAX_OVERALL_DRAWDOWN_PCT:
            dist = config.MAX_OVERALL_DRAWDOWN_PCT - global_drawdown_pct
            msg = f"Global Drawdown ({global_drawdown_pct:.2f}%) breached limit ({config.MAX_OVERALL_DRAWDOWN_PCT}%). Reference Balance: {ref_balance:.2f}."
            await self._trigger_doomsday(msg)
            return False
"""

pattern = r'    async def check_drawdown_limits.*?if start_equity <= 0:\n            return True'
new_content = re.sub(pattern, check_logic.strip(), content, flags=re.DOTALL)

with open('src/execution/risk_manager.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
