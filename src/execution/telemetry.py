import asyncio
import aiohttp
from src.core.event_bus import EventBus, OrderEvent, ErrorEvent, TargetHitEvent, SpikeDetectedEvent, ScoutFailEvent, CommandEvent, SignalEvent
from src.core.config import setup_logger, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = setup_logger("telemetry")

class TelegramTelemetry:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/"
        self.chat_id = TELEGRAM_CHAT_ID
        self._queue = asyncio.Queue()
        self._running = False
        self._offset = 0 # For getUpdates polling
        
        # Subscriptions
        self.event_bus.subscribe(TargetHitEvent, self.handle_target_hit)
        self.event_bus.subscribe(SpikeDetectedEvent, self.handle_spike)
        self.event_bus.subscribe(ErrorEvent, self.handle_error)
        self.event_bus.subscribe(OrderEvent, self.handle_order)
        self.event_bus.subscribe(SignalEvent, self.handle_signal)
        
    async def start(self):
        self._running = True
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or TELEGRAM_BOT_TOKEN == "mock_token":
            logger.info("Telegram Telemetry started in Mock Mode (No token).")
            # We still run the dummy broadcaster to drain the queue
        else:
            logger.info("Production Telegram Telemetry started.")
            
        self.broadcaster_task = asyncio.create_task(self._broadcaster_loop())
        self.commander_task = asyncio.create_task(self._commander_loop())

    async def stop(self):
        self._running = False
        self.broadcaster_task.cancel()
        self.commander_task.cancel()

    async def handle_target_hit(self, event: TargetHitEvent):
        msg = f"🟢 <b>Target Hit!</b>\nCycle ID: {event.cycle_id}\nPnL: ${event.pnl:.2f}"
        await self._queue.put(msg)

    async def handle_spike(self, event: SpikeDetectedEvent):
        msg = f"⚠️ <b>Spike Detected</b>\nCycle ID: {event.cycle_id}\nPrice Diff: {event.price_diff:.5f}\nHalting SET expansion."
        await self._queue.put(msg)

    async def handle_error(self, event: ErrorEvent):
        if event.critical:
            msg = f"🚨 <b>CRITICAL ERROR</b>\nSource: {event.source}\nMessage: {event.message}"
            await self._queue.put(msg)

    async def handle_order(self, event: OrderEvent):
        if event.direction == "CLOSE":
            msg = f"""??? <b>Order Liquidated</b>
Ticket: {event.ticket}
Cycle ID: {event.cycle_id}
Price: {event.price:.5f}
Status: {event.status}"""
            await self._queue.put(msg)
        else:
            msg = f"""? <b>Order Executed</b>
Ticket: {event.ticket}
Cycle ID: {event.cycle_id}
Direction: {event.direction}
Status: {event.status}"""
            await self._queue.put(msg)

    async def handle_signal(self, event: SignalEvent):
        msg = f"""?? <b>Scout/Swarm Triggered</b>
Direction: {event.direction}
Regime: {event.regime}
Conviction: {event.conviction:.2f}"""
        await self._queue.put(msg)

    async def _broadcaster_loop(self):
        while self._running:
            try:
                msg = await self._queue.get()
                if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or TELEGRAM_BOT_TOKEN == "mock_token":
                    logger.info(f"[TELEMETRY MOCK] {msg}")
                    self._queue.task_done()
                    continue
                    
                async with aiohttp.ClientSession() as session:
                    payload = {"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML"}
                    async with session.post(self.url + "sendMessage", json=payload, timeout=5) as resp:
                        if resp.status == 429:
                            logger.warning("Telegram Rate Limit (429).")
                        elif resp.status != 200:
                            logger.error(f"Telegram API Error: {resp.status}")
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Telegram dispatch failed: {e}")
            await asyncio.sleep(0.1) # Small delay to prevent spamming

    async def _commander_loop(self):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or TELEGRAM_BOT_TOKEN == "mock_token":
            return # Don't poll if not configured
            
        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    # Long polling
                    payload = {"offset": self._offset, "timeout": 30}
                    async with session.get(self.url + "getUpdates", params=payload, timeout=35) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("ok"):
                                for update in data.get("result", []):
                                    self._offset = update["update_id"] + 1
                                    message = update.get("message", {})
                                    chat_id = str(message.get("chat", {}).get("id", ""))
                                    text = message.get("text", "").strip()
                                    
                                    if chat_id == self.chat_id:
                                        if text.lower() in ["/panic", "/halt"]:
                                            logger.critical("TELEGRAM COMMAND: PANIC HALT RECEIVED!")
                                            await self.event_bus.publish(CommandEvent(action="PANIC_HALT"))
                                            await self._queue.put("🚨 PANIC HALT INITIATED. Liquidating all positions and locking bridge.")
                                        elif text.lower() == "/status":
                                            logger.info("TELEGRAM COMMAND: STATUS REPORT REQUESTED!")
                                            await self.event_bus.publish(CommandEvent(action="STATUS_REPORT"))
                                        elif text.lower() == "/retrain":
                                            logger.info("TELEGRAM COMMAND: RETRAIN ORACLE REQUESTED!")
                                            await self.event_bus.publish(CommandEvent(action="RETRAIN_ORACLE"))
                                            await self._queue.put("🧠 Initiating Deep Learning Retrain Sequence...")
            except asyncio.CancelledError:
                break
            except asyncio.TimeoutError:
                pass # Expected for long polling
            except Exception as e:
                logger.error(f"Telegram poll error: {e}")
                await asyncio.sleep(5) # Backoff on error
