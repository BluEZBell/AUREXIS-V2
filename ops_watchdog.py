import subprocess
import time
import sys
import logging
import os

# Setup basic logging for the watchdog
logging.basicConfig(
    filename='aurexis_watchdog.log',
    level=logging.INFO,
    format='%(asctime)s - WATCHDOG - %(levelname)s - %(message)s'
)

def main():
    script_path = os.path.join("src", "main.py")
    logging.info(f"Starting AUREXIS Watchdog for {script_path}")
    print("AUREXIS Production Watchdog Online. See aurexis_watchdog.log for details.")
    
    while True:
        try:
            logging.info(f"Launching subprocess: {sys.executable} {script_path}")
            # Start the main bot process
            process = subprocess.Popen([sys.executable, script_path])
            
            # Wait for it to complete
            process.wait()
            
            exit_code = process.returncode
            if exit_code == 0:
                logging.info("AUREXIS exited cleanly. Shutting down Watchdog.")
                print("AUREXIS exited cleanly. Shutting down Watchdog.")
                break
            else:
                logging.error(f"AUREXIS crashed with exit code {exit_code}. Restarting in 10 seconds...")
                print(f"[!] AUREXIS crashed with exit code {exit_code}. Restarting in 10 seconds...")
                time.sleep(10)
                
        except KeyboardInterrupt:
            logging.info("Operator triggered KeyboardInterrupt. Gracefully stopping Watchdog.")
            print("\nOperator triggered KeyboardInterrupt. Stopping Watchdog.")
            if 'process' in locals() and process.poll() is None:
                process.terminate()
                process.wait()
            break
        except Exception as e:
            logging.critical(f"Watchdog encountered a fatal error: {e}")
            print(f"[CRITICAL] Watchdog encountered a fatal error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
