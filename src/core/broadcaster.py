import asyncio
import aiohttp
import logging
from typing import Dict, Any, Union

logger = logging.getLogger("broadcaster")

class TelegramBroadcaster:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token: str = bot_token
        self.chat_id: str = chat_id
        self.queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Union[asyncio.Task, None] = None
        self.api_url: str = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
    async def start(self) -> None:
        """Starts the background worker for consuming and sending messages."""
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker())
            logger.info("TelegramBroadcaster worker started.")

    async def stop(self) -> None:
        """Stops the background worker gracefully."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
            logger.info("TelegramBroadcaster worker stopped.")

    async def broadcast(self, message: Union[str, Dict[str, Any]]) -> None:
        """Adds a message to the broadcasting queue."""
        if isinstance(message, dict):
            # Try to format dictionary to string
            try:
                text = "\n".join([f"{k}: {v}" for k, v in message.items()])
            except Exception:
                text = str(message)
        else:
            text = str(message)
            
        await self.queue.put(text)

    async def _worker(self) -> None:
        """Background worker that processes the message queue."""
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    message: str = await self.queue.get()
                    
                    payload = {
                        "chat_id": self.chat_id,
                        "text": message,
                        "parse_mode": "HTML"
                    }
                    
                    try:
                        async with session.post(self.api_url, json=payload, timeout=10) as response:
                            if response.status == 200:
                                self.queue.task_done()
                            elif response.status == 429:
                                retry_after = response.headers.get("Retry-After", "5")
                                try:
                                    sleep_time = int(retry_after)
                                except ValueError:
                                    sleep_time = 5
                                logger.warning(f"Telegram API Rate Limit Hit (429). Backing off for {sleep_time}s.")
                                await asyncio.sleep(sleep_time)
                                await self.queue.put(message)
                                self.queue.task_done()
                            else:
                                logger.error(f"Telegram API Error: {response.status} - {await response.text()}")
                                # Still mark as done to drop it and prevent infinite loops on bad requests
                                self.queue.task_done()
                    except asyncio.TimeoutError:
                        logger.error("Telegram API Request Timeout. Re-queueing message.")
                        await asyncio.sleep(2)
                        await self.queue.put(message)
                        self.queue.task_done()
                    except aiohttp.ClientError as e:
                        logger.error(f"Telegram API Client Error: {e}. Dropping message.")
                        self.queue.task_done()
                        
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Unexpected error in TelegramBroadcaster worker: {e}")
                    # Sleep to prevent tight failure loop
                    await asyncio.sleep(1)
