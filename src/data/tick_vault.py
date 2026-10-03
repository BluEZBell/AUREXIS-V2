from typing import Any, Dict, List, Optional, Tuple, Union, Callable
import asyncio
import os
import csv

class TickVault:
    def __init__(self, batch_size: int = 1000, filename: str = "live_ticks.csv"):
        self.batch_size = batch_size
        self.filename = filename
        self._buffer: List[Tuple[float, float, float, float, float]] = []
        self._lock = asyncio.Lock()
        
        # Ensure file exists and write header if needed
        if not os.path.exists(self.filename):
            with open(self.filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Bid", "Ask", "Spread", "Volume"])

    async def record_tick(self, timestamp: float, bid: float, ask: float, spread: float, volume: float) -> None:
        """
        O(1) asynchronous method to append tick to buffer.
        """
        self._buffer.append((timestamp, bid, ask, spread, volume))
        if len(self._buffer) >= self.batch_size:
            # Thread-safe buffer clear by atomic reassignment
            data_to_flush = self._buffer
            self._buffer = []
            # Dispatch background task strictly without asyncio.sleep
            asyncio.create_task(self._flush_to_disk(data_to_flush))

    async def _flush_to_disk(self, data: List[Tuple[float, float, float, float, float]]) -> None:
        """
        Flush data to disk asynchronously in a separate thread to prevent blocking.
        Protected by asyncio.Lock to prevent concurrent file access on Windows.
        """
        async with self._lock:
            await asyncio.to_thread(self._write_csv, data)

    def _write_csv(self, data: List[Tuple[float, float, float, float, float]]) -> None:
        with open(self.filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
