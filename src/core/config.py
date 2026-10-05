import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import threading

load_dotenv()

MT5_LOCK = threading.RLock()

async def run_mt5_task(func, *args, **kwargs):
    import asyncio
    import time
    def wrapper():
        if not MT5_LOCK.acquire(timeout=5.0):
            raise TimeoutError("MT5_LOCK contention timeout. Potential broker hang.")
        try:
            return func(*args, **kwargs)
        finally:
            MT5_LOCK.release()
    return await asyncio.to_thread(wrapper)

MAGIC_NUMBER = int(os.getenv("MAGIC_NUMBER", "777999"))
TRADING_SYMBOL = str(os.getenv("TRADING_SYMBOL", "GOLD")).strip().strip('\"').strip('\'')
PROFILE_MODE = os.getenv("PROFILE_MODE", "UNLIMITED_APEX")
WEB_PORT = int(os.getenv("WEB_DASHBOARD_PORT", "8000"))
MT5_TERMINAL_PATH = os.getenv("MT5_PATH") or os.getenv("MT5_TERMINAL_PATH")
if MT5_TERMINAL_PATH:
    MT5_TERMINAL_PATH = MT5_TERMINAL_PATH.replace('\t', '\\t')
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEMETRY_WEBHOOK_URL = os.getenv("TELEMETRY_WEBHOOK_URL", "")

# Macro Configurations
MACRO_DXY = str(os.getenv("MACRO_DXY", "USDX")).strip()
MACRO_SP500 = str(os.getenv("MACRO_SP500", "US500Cash")).strip()
MACRO_VIX = str(os.getenv("MACRO_VIX", "VOLX")).strip()
MACRO_OIL = str(os.getenv("MACRO_OIL", "OILMn")).strip()
MACRO_EURUSD = str(os.getenv("MACRO_EURUSD", "EURUSD")).strip()
MACRO_US10Y = str(os.getenv("MACRO_US10Y", "US10YCash")).strip()
MACRO_USDJPY = str(os.getenv("MACRO_USDJPY", "USDJPY")).strip()
MACRO_XAGUSD = str(os.getenv("MACRO_XAGUSD", "SILVER")).strip()
MACRO_USDCNH = str(os.getenv("MACRO_USDCNH", "USDCNH")).strip()

# Phase 14: Hyper-Parameter Calibration
CHOP_ADX_THRESHOLD = 22.0
PROBE_CONVICTION_MIN = 0.0
CORE_CONVICTION_MIN = 0.0
MAX_CONSECUTIVE_PROBE_FAILS = 9999
MACRO_WIN_PNL_THRESHOLD = 0.0

# Phase 17: The Weekend Flat-Line Protocol
MONDAY_RESUME_HOUR = 0

# Phase 18: Advanced Session Routing & Spread Validation
MAX_ALLOWED_SPREAD_POINTS = 99999
ALLOWED_SESSIONS_STR = "00:00-23:59"

# Phase 21: The High-Water Mark Guardian
DRAWDOWN_TYPE = os.getenv("DRAWDOWN_TYPE", "BALANCE")
INITIAL_ACCOUNT_BALANCE = 100.0

def parse_sessions(session_str: str):
    sessions = []
    for part in session_str.split(','):
        if '-' in part:
            start, end = part.split('-')
            sessions.append({"start": start.strip(), "end": end.strip()})
    return sessions

ALLOWED_SESSIONS = parse_sessions(ALLOWED_SESSIONS_STR)

# Phase 19: Prop-Firm Timezone Synchronization
PROP_FIRM_RESET_TZ = os.getenv("PROP_FIRM_RESET_TZ", "Europe/Prague")
PROP_FIRM_RESET_HOUR = int(os.getenv("PROP_FIRM_RESET_HOUR", "0"))

def setup_logger(name: str) -> logging.Logger:
    from src.core.logger import setup_async_logger
    return setup_async_logger(name)


# --- PHASE 5: Secure Execution & Dry Run ---
MT5_LOGIN = os.getenv("MT5_LOGIN", "")
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
DRY_RUN = os.getenv("DRY_RUN", "False").lower() in ["true", "1", "yes"]

# --- Daily Calibration Variables (Decoupled) ---
BASE_LOT_SIZE = float(os.getenv("BASE_LOT_SIZE", "0.01"))
ASYMMETRIC_KELLY_MULTIPLIER = float(os.getenv("ASYMMETRIC_KELLY_MULTIPLIER", "1.25"))
MAX_SLIPPAGE_POINTS = float(os.getenv("TOXIC_SLIPPAGE_THRESHOLD", "3.0"))

