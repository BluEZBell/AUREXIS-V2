import asyncio
import json
import time
import os
from typing import Dict, Any, Optional

class TelemetryLogger:
    def __init__(self, log_path: str = "telemetry_logs.jsonl", journal_path: str = "trade_journal.csv") -> None:
        self._queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._running: bool = False
        self._worker_task: Optional[asyncio.Task[None]] = None
        self.log_path: str = log_path
        self.journal_path: str = journal_path
        self._trade_closed_callbacks = []

    def register_trade_closed_callback(self, callback) -> None:
        self._trade_closed_callbacks.append(callback)

    async def start(self) -> None:
        self._running = True
        directory: str = os.path.dirname(self.log_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        journal_dir: str = os.path.dirname(self.journal_path)
        if journal_dir:
            os.makedirs(journal_dir, exist_ok=True)
        
        # Write CSV header if file doesn't exist
        if not os.path.exists(self.journal_path):
            with open(self.journal_path, 'w') as f:
                f.write("Order Ticket,Direction,Entry Price,Exit Price,Conviction Score,Slippage,Tick-to-Trade Latency,Total Holding Time,Final PnL,MFE,MAE\n")

        self._worker_task = asyncio.create_task(self._consume_queue())

    async def stop(self) -> None:
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    def record_latency(self, signal_generation_time: float, fill_time: float, ticket: int, symbol: str) -> None:
        payload: Dict[str, Any] = {
            "type": "latency",
            "timestamp": time.time(),
            "signal_generation_time": signal_generation_time,
            "fill_time": fill_time,
            "latency_ms": (fill_time - signal_generation_time) * 1000.0,
            "ticket": ticket,
            "symbol": symbol
        }
        self._queue.put_nowait(payload)

    def record_slippage(self, requested_price: float, fill_price: float, ticket: int, symbol: str, direction: str) -> None:
        slippage: float = fill_price - requested_price if direction == "BUY" else requested_price - fill_price

        payload: Dict[str, Any] = {
            "type": "slippage",
            "timestamp": time.time(),
            "requested_price": requested_price,
            "fill_price": fill_price,
            "slippage": slippage,
            "ticket": ticket,
            "symbol": symbol,
            "direction": direction
        }
        self._queue.put_nowait(payload)

    def record_sentinel_event(self, event_name: str, ticket: int, reason: str) -> None:
        payload: Dict[str, Any] = {
            "type": "sentinel",
            "timestamp": time.time(),
            "event_name": event_name,
            "ticket": ticket,
            "reason": reason
        }
        self._queue.put_nowait(payload)

    def record_trade_closed(self, trade_data: Dict[str, Any]) -> None:
        payload: Dict[str, Any] = {
            "type": "TRADE_CLOSED",
            "timestamp": time.time(),
            **trade_data
        }
        self._queue.put_nowait(payload)
        
        for cb in self._trade_closed_callbacks:
            try:
                cb(trade_data)
            except Exception:
                pass

    async def _consume_queue(self) -> None:
        has_aiofiles: bool = False
        try:
            import aiofiles
            has_aiofiles = True
        except ImportError:
            pass

        if has_aiofiles:
            async with aiofiles.open(self.log_path, mode='a') as f_log, aiofiles.open(self.journal_path, mode='a') as f_journal:
                while self._running:
                    try:
                        item: Dict[str, Any] = await self._queue.get()
                        if item.get("type") == "TRADE_CLOSED":
                            # Order Ticket,Direction,Entry Price,Exit Price,Conviction Score,Slippage,Tick-to-Trade Latency,Total Holding Time,Final PnL,MFE,MAE
                            row = f"{item.get('Order Ticket', '')},{item.get('Direction', '')},{item.get('Entry Price', '')},{item.get('Exit Price', '')},{item.get('Conviction Score', '')},{item.get('Slippage', '')},{item.get('Tick-to-Trade Latency', '')},{item.get('Total Holding Time', '')},{item.get('Final PnL', '')},{item.get('MFE', '')},{item.get('MAE', '')}\n"
                            await f_journal.write(row)
                        else:
                            await f_log.write(json.dumps(item) + '\n')
                        self._queue.task_done()
                    except asyncio.CancelledError:
                        break
                    except Exception:
                        pass
        else:
            # Fallback to executor for file writing, batching to avoid excessive thread creation
            while self._running:
                try:
                    item = await self._queue.get()
                    lines_log: list[str] = []
                    lines_journal: list[str] = []
                    
                    if item.get("type") == "TRADE_CLOSED":
                        row = f"{item.get('Order Ticket', '')},{item.get('Direction', '')},{item.get('Entry Price', '')},{item.get('Exit Price', '')},{item.get('Conviction Score', '')},{item.get('Slippage', '')},{item.get('Tick-to-Trade Latency', '')},{item.get('Total Holding Time', '')},{item.get('Final PnL', '')},{item.get('MFE', '')},{item.get('MAE', '')}\n"
                        lines_journal.append(row)
                    else:
                        lines_log.append(json.dumps(item) + '\n')
                    self._queue.task_done()
                    
                    # Drain queue to batch writes if items are waiting
                    while not self._queue.empty():
                        try:
                            item = self._queue.get_nowait()
                            if item.get("type") == "TRADE_CLOSED":
                                row = f"{item.get('Order Ticket', '')},{item.get('Direction', '')},{item.get('Entry Price', '')},{item.get('Exit Price', '')},{item.get('Conviction Score', '')},{item.get('Slippage', '')},{item.get('Tick-to-Trade Latency', '')},{item.get('Total Holding Time', '')},{item.get('Final PnL', '')},{item.get('MFE', '')},{item.get('MAE', '')}\n"
                                lines_journal.append(row)
                            else:
                                lines_log.append(json.dumps(item) + '\n')
                            self._queue.task_done()
                        except asyncio.QueueEmpty:
                            break
                            
                    await asyncio.to_thread(self._sync_write_batch, lines_log, lines_journal)
                except asyncio.CancelledError:
                    break
                except Exception:
                    pass

    def _sync_write_batch(self, lines_log: list[str], lines_journal: list[str]) -> None:
        if lines_log:
            with open(self.log_path, 'a') as f:
                f.writelines(lines_log)
        if lines_journal:
            with open(self.journal_path, 'a') as f:
                f.writelines(lines_journal)
