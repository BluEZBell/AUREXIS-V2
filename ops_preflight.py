"""
AUREXIS V2 Pre-Flight Health Check
Phase 9: The Pre-Flight Health Check (Standalone Operational Script)
Verifies MT5 connectivity, network latency, account margin, and database integrity.
"""

import asyncio
import logging
import sys
import sqlite3
import os
import MetaTrader5 as mt5
from src.core import config

# Setup strict logging for the Pre-Flight script
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("PreFlight")

class PreFlightChecker:
    def __init__(self):
        self.db_path = "db/aurexis_ledger.db"

    async def _init_mt5(self) -> bool:
        """Initialize MetaTrader 5 Connection"""
        if not mt5.initialize(path=config.MT5_TERMINAL_PATH):
            logger.error(f"[FAIL] MT5 Initialization failed: {mt5.last_error()}")
            return False
        return True

    async def check_connectivity(self) -> bool:
        """Check Terminal Connectivity"""
        terminal_info = mt5.terminal_info()
        if terminal_info is None:
            logger.error(f"[FAIL] Failed to retrieve MT5 Terminal Info: {mt5.last_error()}")
            return False
        
        if not terminal_info.connected:
            logger.error("[FAIL] MT5 is NOT connected to the broker server.")
            return False
        
        logger.info(f"[PASS] MT5 Connected: {terminal_info.name} ({terminal_info.company})")
        return True

    async def check_latency(self) -> bool:
        """Check Network Latency (Ping)"""
        terminal_info = mt5.terminal_info()
        if terminal_info is None:
            logger.error("[FAIL] Cannot retrieve terminal info for latency check.")
            return False

        ping = terminal_info.ping_last
        if ping == 0:
            logger.warning("[WARN] Ping is 0 (Could be disconnected or local server).")
        elif ping > 100000:
            logger.warning(f"[WARN] Severe Network Latency Detected: {ping/1000:.1f}ms. Broker connection is unstable.")
        else:
            logger.info(f"[PASS] Network Latency OK: {ping/1000:.1f}ms")
            
        return True

    async def check_margin(self) -> bool:
        """Check Account Free Margin"""
        account_info = mt5.account_info()
        if account_info is None:
            logger.error(f"[FAIL] Failed to retrieve MT5 Account Info: {mt5.last_error()}")
            return False
            
        margin_free = account_info.margin_free
        
        if margin_free <= 50.0:
            logger.error(f"[FAIL] Insufficient Free Margin: ${margin_free:.2f}. Minimum required is > $50.00.")
            return False
            
        logger.info(f"[PASS] Free Margin OK: ${margin_free:.2f}")
        return True

    async def check_database(self) -> bool:
        """Check SQLite Database Integrity and Access"""
        if not os.path.exists(self.db_path):
            logger.info(f"[PASS] Database file {self.db_path} does not exist yet. It will be created on startup.")
            return True
            
        try:
            # Attempt a read-only connection to ensure it's not exclusively locked
            uri_path = f"file:{os.path.abspath(self.db_path)}?mode=ro"
            conn = sqlite3.connect(uri_path, uri=True)
            cursor = conn.cursor()
            # Simple query to verify access
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            cursor.fetchall()
            conn.close()
            logger.info(f"[PASS] Database Integrity OK. {self.db_path} is accessible and unlocked.")
            return True
        except sqlite3.OperationalError as e:
            logger.error(f"[FAIL] Database is locked or inaccessible: {e}")
            return False
        except Exception as e:
            logger.error(f"[FAIL] Unexpected error during database check: {e}")
            return False

    async def run_all_checks(self):
        logger.info("Starting AUREXIS Pre-Flight Health Check...")
        
        if not await self._init_mt5():
            sys.exit(1)
            
        checks_passed = True
        
        # Critical Check 1: Connectivity
        if not await self.check_connectivity():
            checks_passed = False
            
        # Warning Check: Latency
        if checks_passed:
            await self.check_latency()
            
        # Critical Check 2: Margin
        if checks_passed and not await self.check_margin():
            checks_passed = False
            
        # Critical Check 3: Database
        if checks_passed and not await self.check_database():
            checks_passed = False
            
        mt5.shutdown()
        
        if not checks_passed:
            logger.error("Pre-Flight Checks FAILED. Do NOT launch the Watchdog.")
            sys.exit(1)
            
        logger.info("All Systems GO. AUREXIS is ready for ignition.")
        sys.exit(0)

if __name__ == "__main__":
    checker = PreFlightChecker()
    asyncio.run(checker.run_all_checks())
