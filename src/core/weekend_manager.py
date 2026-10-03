import asyncio
import datetime
from src.core.event_bus import EventBus, WeekendBlackoutEvent
from src.core.config import setup_logger, MONDAY_RESUME_HOUR

logger = setup_logger("weekend_manager")

class WeekendManager:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._running = False
        self._is_weekend_blackout = False

    async def start(self):
        self._running = True
        logger.info("WeekendManager started. Monitoring for Weekend Flat-Line Protocol.")
        asyncio.create_task(self._run_loop())

    async def stop(self):
        self._running = False

    async def _run_loop(self):
        while self._running:
            try:
                # MT5 server time closely matches UTC/EET. We use local/UTC time abstraction.
                # Assuming the strategy relies on standard datetime.utcnow() or server time.
                # Since server time isn't explicitly passed here, we'll use datetime.utcnow()
                # Assuming MT5 server time is UTC+2 or UTC+3, we check current UTC.
                # To be precise, let's use the local datetime assuming the VPS is on Server time,
                # or just use datetime.datetime.now() which is typically aligned if VPS is set up correctly.
                now = datetime.datetime.now()
                
                # weekday(): 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
                is_friday_halt = False
                is_weekend = (now.weekday() in [5, 6])
                is_monday_pre_open = (now.weekday() == 0 and now.hour < MONDAY_RESUME_HOUR)
                
                # Execution engine must remain active 24/5. No halts.
                pass
                    
            except Exception as e:
                logger.error(f"Error in WeekendManager loop: {e}")
                
            await asyncio.sleep(60) # Zero blocking code, check every 60 seconds
