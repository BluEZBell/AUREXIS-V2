import asyncio
import aiohttp
from typing import Optional, Set

from src.core.event_bus import EventBus, RiskAlertEvent, CommandEvent
from src.core.config import setup_logger

logger = setup_logger("telemetry_broadcaster")

class TelemetryBroadcaster:
    def __init__(self, event_bus: EventBus, webhook_url: str):
        self.event_bus = event_bus
        self.webhook_url = webhook_url
        self._session: Optional[aiohttp.ClientSession] = None
        self._tasks: Set[asyncio.Task] = set()

        self.event_bus.subscribe(RiskAlertEvent, self._on_risk_alert)
        self.event_bus.subscribe(CommandEvent, self._on_command_event)

    async def start(self):
        if not self.webhook_url:
            logger.warning("TelemetryBroadcaster: No webhook URL configured.")
            return
        self._session = aiohttp.ClientSession()
        logger.info("TelemetryBroadcaster started.")

    async def stop(self):
        # Cancel all pending background tasks
        for task in self._tasks:
            task.cancel()
            
        if self._tasks:
            # Await its task(s) during shutdown
            await asyncio.gather(*self._tasks, return_exceptions=True)
            
        if self._session and not self._session.closed:
            await self._session.close()
            
        logger.info("TelemetryBroadcaster stopped.")

    async def _on_risk_alert(self, event: RiskAlertEvent):
        if event.level in ("WARNING", "CRITICAL"):
            payload = {
                "content": f"🚨 **RISK ALERT ({event.level})** 🚨\n{event.message}"
            }
            self.fire_and_forget_webhook(payload)

    async def _on_command_event(self, event: CommandEvent):
        if event.action == "100_PCT_ROI_VAULT_SECURED":
            payload = {
                "content": f"🏆 **MILESTONE SECURED** 🏆\n100% ROI Vault Locked. You may now relax."
            }
            self.fire_and_forget_webhook(payload)

    def fire_and_forget_webhook(self, payload: dict):
        if not self._session or not self.webhook_url:
            return

        async def _send():
            try:
                # Wrap network call in strict 2-second timeout
                await asyncio.wait_for(
                    self._session.post(self.webhook_url, json=payload),
                    timeout=2.0
                )
            except Exception as e:
                # Silently swallow any network errors to prevent blocking the EventBus
                logger.debug(f"TelemetryBroadcaster network error: {e}")
                pass

        # Add it to the background tasks loop (fire and forget)
        task = asyncio.create_task(_send())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
