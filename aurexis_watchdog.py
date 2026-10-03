import os
import sys
import time
import subprocess
import logging
from logging.handlers import RotatingFileHandler

def setup_watchdog_logger():
    logger = logging.getLogger("watchdog")
    logger.setLevel(logging.INFO)
    
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "watchdog.log"), 
        maxBytes=1048576, # 1MB
        backupCount=3,
        encoding='utf-8'
    )
    stream_handler = logging.StreamHandler(sys.stdout)
    
    formatter = logging.Formatter('%(asctime)s - AUREXIS WATCHDOG - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger

def main():
    logger = setup_watchdog_logger()
    logger.info("Initializing AUREXIS OS-Level Watchdog...")
    
    script_to_run = [sys.executable, os.path.join("src", "main.py"), "--no-ui"]
    
    # If the user specifically wants the UI when launching via watchdog
    if "--ui" in sys.argv:
        script_to_run.remove("--no-ui")

    consecutive_crashes = 0
    backoff_seconds = 10
    
    while True:
        logger.info(f"Launching AUREXIS Process: {' '.join(script_to_run)}")
        
        try:
            # Launch the bot as a decoupled subprocess
            process = subprocess.Popen(script_to_run)
            
            # Watchdog sleeps and waits for the process to exit
            process.wait()
            
            exit_code = process.returncode
            
            if exit_code == 0:
                logger.info("AUREXIS Process exited cleanly (Code 0). Watchdog shutting down.")
                break
            else:
                consecutive_crashes += 1
                logger.error(f"AUREXIS Process CRASHED with exit code {exit_code}.")
                
                # Dynamic backoff to prevent tight crash loops
                wait_time = min(backoff_seconds * consecutive_crashes, 60)
                logger.warning(f"Watchdog will restart AUREXIS in {wait_time} seconds (Crash count: {consecutive_crashes})...")
                time.sleep(wait_time)
                
        except KeyboardInterrupt:
            logger.warning("Operator manually stopped the Watchdog (KeyboardInterrupt).")
            if 'process' in locals() and process.poll() is None:
                logger.warning("Terminating AUREXIS Subprocess...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.critical("Subprocess refused to terminate. Force killing.")
                    process.kill()
            break
        except Exception as e:
            logger.critical(f"Watchdog encountered a catastrophic error: {e}")
            time.sleep(30) # Sleep and retry so the watchdog itself doesn't crash in a tight loop

    logger.info("AUREXIS Watchdog deactivated. System Offline.")

if __name__ == "__main__":
    main()
