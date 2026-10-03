import asyncio
import aiohttp
from src.core.event_bus import EventBus, OrderEvent, ErrorEvent
from src.core.config import setup_logger, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = setup_logger("telegram")

class TelegramNotifier:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        self.chat_id = TELEGRAM_CHAT_ID
        
        self.event_bus.subscribe(OrderEvent, self.handle_order)
        self.event_bus.subscribe(ErrorEvent, self.handle_error)

    async def _send_message(self, text: str):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or TELEGRAM_BOT_TOKEN == "mock_token":
            logger.info(f"Mock Telegram Alert: {text}")
            return
            
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
                async with session.post(self.url, json=payload) as resp:
                    if resp.status == 429:
                        logger.warning("Telegram Rate Limit (429). Dropping alert.")
                    elif resp.status != 200:
                        logger.error(f"Telegram API Error: {resp.status}")
        except Exception as e:
            logger.error(f"Telegram dispatch failed: {e}")

    async def handle_order(self, event: OrderEvent):
        emoji = "🟢" if event.direction == "BUY" else "🔴"
        if event.direction == "CLOSE": emoji = "🏁"
        if event.direction == "MODIFY_SL": emoji = "🛡️"
        
        msg = f"{emoji} <b>Order Event</b>\nSymbol: {event.symbol}\nAction: {event.direction}\nStatus: {event.status}\nPrice: {event.price}"
        asyncio.create_task(self._send_message(msg))

    async def handle_error(self, event: ErrorEvent):
        emoji = "🛑" if event.critical else "⚠️"
        msg = f"{emoji} <b>System Alert</b>\nSource: {event.source}\nMessage: {event.message}"
        asyncio.create_task(self._send_message(msg))
