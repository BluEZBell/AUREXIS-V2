import asyncio
import logging
import sys
import os
import signal
from datetime import datetime, time, timedelta
from typing import Optional
import subprocess
import webbrowser

# Configure logging
from src.core.logger import setup_async_logger
setup_async_logger()

# Constants
BASE_DIR: str = r"C:\Users\bluzp\AUREXISV2"
PREFLIGHT_SCRIPT: str = os.path.join(BASE_DIR, "preflight_diagnostic.py")
MAIN_SCRIPT: str = os.path.join(BASE_DIR, "main.py")
EOD_TEARSHEET_SCRIPT: str = os.path.join(BASE_DIR, "eod_tearsheet.py")
ALPHA_TUNER_SCRIPT: str = os.path.join(BASE_DIR, "alpha_tuner.py")

EOD_TIME: time = time(23, 55)
RESTART_COOLDOWN: float = 10.0

class Supervisor:
    def __init__(self) -> None:
        self.main_process: Optional[asyncio.subprocess.Process] = None
        self.shutdown_event: asyncio.Event = asyncio.Event()
        self.eod_triggered: bool = False

    async def run_preflight(self) -> bool:
        logging.info("Starting Pre-Flight Diagnostic...")
        if not os.path.exists(PREFLIGHT_SCRIPT):
            logging.warning(f"Pre-flight script not found at {PREFLIGHT_SCRIPT}. Assuming success for testing.")
            return True

        process: asyncio.subprocess.Process = await asyncio.create_subprocess_exec(
            sys.executable, PREFLIGHT_SCRIPT,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=BASE_DIR
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logging.error(f"FATAL: Pre-Flight Diagnostic failed with exit code {process.returncode}.")
            if stdout:
                logging.error(f"Stdout:\n{stdout.decode().strip()}")
            if stderr:
                logging.error(f"Stderr:\n{stderr.decode().strip()}")
            return False
            
        logging.info("Pre-Flight Diagnostic passed.")
        if stdout:
            logging.info(f"Pre-Flight Output:\n{stdout.decode().strip()}")
        return True

    async def _terminate_main_process(self) -> None:
        if self.main_process and self.main_process.returncode is None:
            logging.info("Terminating Main Engine gracefully...")
            
            # On Windows, try CTRL_C_EVENT for graceful shutdown if CREATE_NEW_PROCESS_GROUP was used
            try:
                if sys.platform == 'win32':
                    os.kill(self.main_process.pid, signal.CTRL_C_EVENT)
                else:
                    self.main_process.terminate()
            except (AttributeError, ProcessLookupError, OSError):
                try:
                    self.main_process.terminate()
                except ProcessLookupError:
                    pass
            
            try:
                await asyncio.wait_for(self.main_process.wait(), timeout=10.0)
                logging.info("Main Engine terminated gracefully.")
            except asyncio.TimeoutError:
                logging.warning("Main Engine did not terminate gracefully within 10s. Killing process.")
                try:
                    self.main_process.kill()
                    await self.main_process.wait()
                except ProcessLookupError:
                    pass

    async def manage_main_engine(self) -> None:
        creationflags = 0
        if sys.platform == 'win32':
            creationflags = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)

        try:
            while not self.shutdown_event.is_set():
                logging.info("Starting Main Trading Engine...")
                if not os.path.exists(MAIN_SCRIPT):
                    logging.error(f"Main script not found at {MAIN_SCRIPT}. Aborting.")
                    self.shutdown_event.set()
                    return

                self.main_process = await asyncio.create_subprocess_exec(
                    sys.executable, MAIN_SCRIPT,
                    cwd=BASE_DIR,
                    creationflags=creationflags
                )
                
                shutdown_task: asyncio.Task = asyncio.create_task(self.shutdown_event.wait())
                process_task: asyncio.Task = asyncio.create_task(self.main_process.wait())
                
                done, pending = await asyncio.wait(
                    [shutdown_task, process_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel pending tasks to prevent memory leaks and "Task destroyed but pending" warnings
                for t in pending:
                    t.cancel()
                
                if self.shutdown_event.is_set():
                    logging.info("Shutdown event received, stopping Main Engine.")
                    break
                else:
                    return_code = self.main_process.returncode
                    if return_code == 0:
                        logging.info("Main Engine exited cleanly.")
                        break
                    else:
                        logging.error(f"Main Engine crashed with exit code {return_code}. Restarting in {RESTART_COOLDOWN} seconds...")
                        # Await the cooldown, but allow interruption if shutdown_event is set during cooldown
                        try:
                            await asyncio.wait_for(self.shutdown_event.wait(), timeout=RESTART_COOLDOWN)
                            logging.info("Shutdown event received during restart cooldown.")
                            break
                        except asyncio.TimeoutError:
                            # Cooldown finished without shutdown, loop restarts main engine
                            pass
        finally:
            await self._terminate_main_process()

    async def wait_for_web_server(self, port: int = 8000, timeout: int = 30) -> None:
        start_time = asyncio.get_running_loop().time()
        logging.info(f"Polling local web server on port {port}...")
        while True:
            if asyncio.get_running_loop().time() - start_time > timeout:
                logging.error("Timeout waiting for web server to start.")
                break
            if self.shutdown_event.is_set():
                break
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.close()
                await writer.wait_closed()
                logging.info("Web server is fully initialized. Opening browser...")
                await asyncio.to_thread(webbrowser.open, f"http://127.0.0.1:{port}")
                break
            except (ConnectionRefusedError, TimeoutError, OSError):
                await asyncio.sleep(1.0)

    async def wait_for_eod(self) -> None:
        # Legacy EOD termination eradicated
        pass

    async def run_eod_pipeline(self) -> None:
        logging.info("Starting End-of-Day (EOD) Pipeline...")
        
        # 1. Run eod_tearsheet.py
        if os.path.exists(EOD_TEARSHEET_SCRIPT):
            logging.info("Running EOD Tearsheet generator...")
            tearsheet_process: asyncio.subprocess.Process = await asyncio.create_subprocess_exec(
                sys.executable, EOD_TEARSHEET_SCRIPT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=BASE_DIR
            )
            stdout, stderr = await tearsheet_process.communicate()
            logging.info(f"EOD Tearsheet generator finished with exit code {tearsheet_process.returncode}.")
            if stdout:
                logging.info(f"Tearsheet Output (Report Path & Details):\n{stdout.decode().strip()}")
            if stderr:
                logging.error(f"Tearsheet Errors:\n{stderr.decode().strip()}")
        else:
            logging.warning(f"Tearsheet script not found at {EOD_TEARSHEET_SCRIPT}.")

        # 2. Run alpha_tuner.py
        if os.path.exists(ALPHA_TUNER_SCRIPT):
            logging.info("Running Alpha Tuner...")
            tuner_process: asyncio.subprocess.Process = await asyncio.create_subprocess_exec(
                sys.executable, ALPHA_TUNER_SCRIPT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=BASE_DIR
            )
            stdout, stderr = await tuner_process.communicate()
            logging.info(f"Alpha Tuner finished with exit code {tuner_process.returncode}.")
            if stdout:
                logging.info(f"Tuner Output (Final Tuned Parameters):\n{stdout.decode().strip()}")
            if stderr:
                logging.error(f"Tuner Errors:\n{stderr.decode().strip()}")
        else:
            logging.warning(f"Alpha Tuner script not found at {ALPHA_TUNER_SCRIPT}.")

        logging.info("EOD Pipeline completed successfully.")

    async def start(self) -> None:
        logging.info("AUREXIS Institutional Process Supervisor starting...")
        
        # Step 1: Pre-Flight
        if not await self.run_preflight():
            logging.error("Launch aborted due to Pre-Flight failure.")
            return
            
        # Step 2 & 3: Run main engine, wait for EOD, and orchestrate web dashboard
        engine_task: asyncio.Task = asyncio.create_task(self.manage_main_engine())
        eod_task: asyncio.Task = asyncio.create_task(self.wait_for_eod())
        web_task: asyncio.Task = asyncio.create_task(self.wait_for_web_server(port=8000, timeout=30))
        
        # Wait until shutdown event is set (via KeyboardInterrupt, or critical failure)
        await self.shutdown_event.wait()
        
        if not eod_task.done():
            eod_task.cancel()
        if not web_task.done():
            web_task.cancel()
            
        # Wait for the main engine to gracefully terminate (managed by its finally block)
        await engine_task

def main() -> None:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    supervisor = Supervisor()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    main_task = loop.create_task(supervisor.start())
    
    # Handle graceful shutdown on Windows (Ctrl+C)
    try:
        loop.run_until_complete(main_task)
    except KeyboardInterrupt:
        logging.info("Received KeyboardInterrupt. Shutting down Supervisor...")
        supervisor.shutdown_event.set()
        # Allow time for graceful shutdown
        try:
            loop.run_until_complete(main_task)
        except asyncio.CancelledError:
            pass
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()

if __name__ == "__main__":
    main()
