import time
import logging
from collections import deque
from src.core.event_bus import EventBus, MacroUpdateEvent, CommandEvent, ErrorEvent
from src.core.config import setup_logger

logger = setup_logger("macro_guardian")

class MacroGuardian:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.event_bus.subscribe(MacroUpdateEvent, self.handle_macro_update)
        
        # State
        self.dxy_history = deque(maxlen=3)
        self.last_trigger_time = 0.0
        self.cooldown_duration = 900.0  # 15 minutes cooldown

        logger.info("Macro Black Swan Guardian initialized.")

    async def handle_macro_update(self, event: MacroUpdateEvent):
        # Ignore historical updates from init phase
        if getattr(event, "is_historical", False):
            return

        current_time = time.time()
        
        # No Cooldown applied

        # Maintain DXY History
        self.dxy_history.append(event.dxy)

        triggered = False
        trigger_reason = ""

        # Condition 1: Extreme Market Fear (VIX >= 25.0)
        if event.vix >= 25.0:
            triggered = True
            trigger_reason = f"Extreme VIX Spike ({event.vix:.2f})"

        # Condition 2: DXY Velocity Spike (> 0.15 within last 3 updates)
        if not triggered and len(self.dxy_history) == 3:
            dxy_min = min(self.dxy_history)
            dxy_max = max(self.dxy_history)
            delta = dxy_max - dxy_min
            if delta > 0.15:
                triggered = True
                trigger_reason = f"DXY Velocity Shock (Delta: {delta:.3f})"

        if triggered:
            logger.critical(f"MACRO VOLATILITY DETECTED: {trigger_reason}. Adapting AlphaScorer regime.")
            self.last_trigger_time = current_time

            # Adapt dynamically instead of halting
            await self.event_bus.publish(CommandEvent(action="MACRO_ADAPT"))

            # Publish Warning instead of Critical Error
            await self.event_bus.publish(ErrorEvent(
                source="MacroGuardian",
                message=f"MACRO VOLATILITY DETECTED. ADAPTING SIZING/SL.\nReason: {trigger_reason}",
                critical=False
            ))
