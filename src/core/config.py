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
MACRO_DXY_ALIASES = [x.strip() for x in os.getenv("MACRO_DXY_ALIASES", "USDX,DXY,USDOLLAR,DX").split(',')]
MACRO_SP500_ALIASES = [x.strip() for x in os.getenv("MACRO_SP500_ALIASES", "US500Cash,US500,SPX,SP500,S&P500").split(',')]
MACRO_VIX_ALIASES = [x.strip() for x in os.getenv("MACRO_VIX_ALIASES", "VOLX,VIX,VIX.c").split(',')]
MACRO_OIL_ALIASES = [x.strip() for x in os.getenv("MACRO_OIL_ALIASES", "OILMn,USOIL,WTI,XTIUSD,USCRUDE").split(',')]
MACRO_EURUSD_ALIASES = [x.strip() for x in os.getenv("MACRO_EURUSD_ALIASES", "EURUSD,EURUSD.,EURUSD#").split(',')]
MACRO_US10Y_ALIASES = [x.strip() for x in os.getenv("MACRO_US10Y_ALIASES", "US10YCash,US10YR,TNOTE,TN").split(',')]
MACRO_USDJPY_ALIASES = [x.strip() for x in os.getenv("MACRO_USDJPY_ALIASES", "USDJPY,USDJPY.,USDJPY#").split(',')]
MACRO_XAGUSD_ALIASES = [x.strip() for x in os.getenv("MACRO_XAGUSD_ALIASES", "SILVER,XAGUSD,XAGUSD.,XAGUSD#").split(',')]
MACRO_USDCNH_ALIASES = [x.strip() for x in os.getenv("MACRO_USDCNH_ALIASES", "USDCNH,USDCNH.,USDCNH#").split(',')]

# Phase 14: Hyper-Parameter Calibration
CHOP_ADX_THRESHOLD = 22.0
PROBE_CONVICTION_MIN = 60.0
CORE_CONVICTION_MIN = 60.0
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


BASE_RISK_PCT = 0.40  # Extreme Aggression (100% Daily Target Override)

MIN_STRUCTURAL_SL_POINTS = float(os.getenv('MIN_STRUCTURAL_SL_POINTS', '200.0'))
