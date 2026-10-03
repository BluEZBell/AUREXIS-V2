import asyncio
import aiohttp
import logging
import os
from src.core.event_bus import EventBus, OrderEvent, RiskAlertEvent, OracleVetoEvent, ErrorEvent, StructuralTrendEvent, MilestoneEvent, SentinelKillEvent
from src.core.config import setup_logger

logger = setup_logger("async_notifier")

class TelegramNotifier:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_TOKEN"))
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self._session = None
        self._running = False
        
        self._first_blood_drawn = False
        self._last_regime = "NEUTRAL"
        self._background_tasks = set()
        
        self.event_bus.subscribe(OrderEvent, self._handle_order_event)
        self.event_bus.subscribe(StructuralTrendEvent, self._handle_regime_shift)
        self.event_bus.subscribe(MilestoneEvent, self._handle_milestone)
        self.event_bus.subscribe(ErrorEvent, self._handle_error_event)
        self.event_bus.subscribe(SentinelKillEvent, self._handle_sentinel_kill)

    async def start(self):
        if not self.token or not self.chat_id:
            logger.warning("TelegramNotifier: TELEGRAM_TOKEN or TELEGRAM_CHAT_ID missing. Silent mode active.")
            return
            
        self._running = True
        self._session = aiohttp.ClientSession()
        logger.info("TelegramNotifier: Started and connected to EventBus.")

    async def stop(self):
        self._running = False
        if self._session and not self._session.closed:
            await self._session.close()
            
        # Cancel all pending background tasks
        for task in list(self._background_tasks):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._background_tasks.clear()
        
        logger.info("TelegramNotifier: Stopped.")

    async def send_message(self, text: str):
        if not self._running or not self._session or not self.token or not self.chat_id:
            return
            
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        
        async def _post():
            try:
                async with self._session.post(url, json=payload, timeout=5) as response:
                    if response.status != 200:
                        logger.error(f"TelegramNotifier: API returned status {response.status}")
            except Exception as e:
                logger.error(f"TelegramNotifier: Network failure - {e}")
                
        task = asyncio.create_task(_post())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _handle_order_event(self, event: OrderEvent):
        if event.status == "FILLED" and event.direction in ["BUY", "SELL"]:
            if not self._first_blood_drawn:
                self._first_blood_drawn = True
                msg = f"🩸 **FIRST BLOOD**\nFirst Naked Execution order successfully filled.\nSymbol: {event.symbol}\nType: {event.order_type} {event.direction}\nTicket: {event.ticket}\nPrice: {event.price:.2f}"
                await self.send_message(msg)
                
        elif event.direction == "MODIFY_SL" and event.status == "FILLED":
            msg = f"⚡ **PYRAMIDING TRIGGERED**\nFloating profit locked. Next aggressive entry authorized.\nTicket: {event.ticket}\nSL Locked At: {event.price:.5f}"
            await self.send_message(msg)

    async def _handle_regime_shift(self, event: StructuralTrendEvent):
        current_trend = event.m15_trend
        if self._last_regime in ["NEUTRAL", "CHOP"] and current_trend in ["BULLISH", "BEARISH"]:
            msg = f"🎯 **REGIME SHIFT**\nRegime transitioned from {self._last_regime} to {current_trend}. Starting momentum hunt!"
            await self.send_message(msg)
        self._last_regime = current_trend

    async def _handle_milestone(self, event: MilestoneEvent):
        if event.milestone_name == "MILESTONE_ACHIEVED":
            msg = f"🏆 **MILESTONE ACHIEVED**\n{event.message}\nBook flatted. Capital secured."
            await self.send_message(msg)

    async def _handle_error_event(self, event: ErrorEvent):
        if getattr(event, 'critical', False):
            msg = f"🔥 **SYSTEM ERROR (CRITICAL)**\nComponent: {event.source}\nMessage: {event.message}"
            await self.send_message(msg)
        elif "LATENCY WARNING" in event.message:
            msg = f"⚠️ **LATENCY WARNING**\nComponent: {event.source}\nMessage: {event.message}"
            await self.send_message(msg)

    async def _handle_sentinel_kill(self, event: SentinelKillEvent):
        if event.reason == "MOMENTUM_EXHAUSTED":
            msg = "[EXHAUSTION KILL] Position closed preemptively due to momentum stall. Profit secured."
            await self.send_message(msg)
