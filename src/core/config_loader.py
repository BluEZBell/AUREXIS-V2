import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger("Aurexis.ConfigLoader")

def load_environment_variables() -> None:
    """
    Loads and validates critical environment variables from the .env file.
    Raises RuntimeError if required variables are missing.
    """
    load_dotenv()
    
    required_vars = [
        "MT5_LOGIN",
        "MT5_PASSWORD",
        "MT5_SERVER",
        "TELEGRAM_TOKEN",
        "TELEGRAM_CHAT_ID"
    ]
    
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
            
    if missing_vars:
        error_msg = f"CRITICAL: Missing or empty environment variables: {', '.join(missing_vars)}"
        logger.critical(error_msg)
        raise RuntimeError(error_msg)
        
    logger.info("Environment variables successfully loaded and validated.")
