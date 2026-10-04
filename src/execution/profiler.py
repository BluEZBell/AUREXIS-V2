import asyncio
import logging
import time
import os
import csv
from typing import Optional

logger = logging.getLogger("execution_profiler")

class ExecutionProfiler:
    def __init__(self, log_path: str = "logs/execution_profiler.csv"):
        self.log_path = log_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        if not os.path.exists(self.log_path):
            with open(self.log_path, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Ticket", "Symbol", "Action", 
                    "Requested_Price", "Filled_Price", 
                    "Slippage_Points", "Latency_MS"
                ])

    async def log_execution(self, ticket: int, symbol: str, action: int, requested_price: float, filled_price: float, slippage_pts: float, latency_ms: float):
        # Unobtrusive console log
        logger.info(f"EXECUTION PROFILER: Ticket {ticket} | Latency: {latency_ms:.2f}ms | Slippage: {slippage_pts:.2f} pts")
        
        # Async disk write
        await asyncio.to_thread(self._write_to_csv, ticket, symbol, action, requested_price, filled_price, slippage_pts, latency_ms)

    def _write_to_csv(self, ticket: int, symbol: str, action: int, requested_price: float, filled_price: float, slippage_pts: float, latency_ms: float):
        try:
            with open(self.log_path, mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    time.strftime('%Y-%m-%d %H:%M:%S'),
                    ticket,
                    symbol,
                    action,
                    requested_price,
                    filled_price,
                    round(slippage_pts, 3),
                    round(latency_ms, 2)
                ])
        except Exception as e:
            logger.error(f"Failed to write to execution_profiler.csv: {e}")
