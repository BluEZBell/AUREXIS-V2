import os
import sys
import asyncio
import signal
from datetime import datetime, time, timedelta
from typing import Optional
import logging

class Supervisor:
    def __init__(self) -> None:
        self.main_process: Optional[asyncio.subprocess.Process] = None
        self.shutdown_event: asyncio.Event = asyncio.Event()
        self.eod_triggered: bool = False
        
    async def manage_main_engine(self):
        logging.info("Main engine loop starting.")
        try:
            while not self.shutdown_event.is_set():
                process_task = asyncio.create_task(asyncio.sleep(1.0))
                shutdown_task = asyncio.create_task(self.shutdown_event.wait())
                
                done, pending = await asyncio.wait(
                    [shutdown_task, process_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                for t in pending:
                    t.cancel()
                    
                if self.shutdown_event.is_set():
                    logging.info("Shutdown event received.")
                    break
        finally:
            logging.info("manage_main_engine finally block executed.")

async def start_supervisor():
    supervisor = Supervisor()
    
    # We will simulate a KeyboardInterrupt by setting the shutdown event after 2 seconds
    async def interrupt():
        await asyncio.sleep(2)
        logging.info("Simulating KeyboardInterrupt...")
        # A real KeyboardInterrupt would raise outside the loop, but this tests task cancellation handling
        supervisor.shutdown_event.set()

    asyncio.create_task(interrupt())
    
    engine_task = asyncio.create_task(supervisor.manage_main_engine())
    
    await supervisor.shutdown_event.wait()
    await engine_task

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_supervisor())
