import asyncio
import os
import time
import MetaTrader5 as mt5
import aiosqlite
import aiohttp
from dotenv import load_dotenv
from typing import Any, Dict, Optional

async def close_position_async(position: Any) -> Any:
    """Closes a single MT5 position asynchronously."""
    tick = await asyncio.to_thread(mt5.symbol_info_tick, position.symbol)
    if tick is None:
        return None
        
    order_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
    
    request: Dict[str, Any] = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": position.symbol,
        "volume": position.volume,
        "type": order_type,
        "position": position.ticket,
        "price": price,
        "deviation": 20,
        "magic": position.magic,
        "comment": "PANIC BUTTON OVERRIDE",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = await asyncio.to_thread(mt5.order_send, request)
    return result

async def flatten_book(magic_number: int) -> None:
    """Queries open positions for a magic number and closes them in parallel."""
    positions = await asyncio.to_thread(mt5.positions_get)
    if positions is None:
        print("No open positions found or failed to retrieve positions.")
        return
        
    filtered_positions = [pos for pos in positions if getattr(pos, 'magic', 0) == magic_number]
    
    if len(filtered_positions) == 0:
        print(f"No open positions found for magic number {magic_number}.")
        return

    print(f"Found {len(filtered_positions)} positions. Dispatching parallel Market Close orders...")
    
    tasks = [close_position_async(pos) for pos in filtered_positions]
    results = await asyncio.gather(*tasks)
    
    success_count = 0
    for r in results:
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            success_count += 1
        else:
            print(f"Failed to close position: {r.comment if hasattr(r, 'comment') else 'Unknown'} / Retcode: {r.retcode if hasattr(r, 'retcode') else 'N/A'}")
            
    print(f"Successfully closed {success_count}/{len(filtered_positions)} positions.")

async def sanitize_state_ledger(db_path: str) -> None:
    """Wipes memory states from the active_tickets table to prevent phantom order recovery."""
    print(f"Sanitizing State Ledger at {db_path}...")
    try:
        # Include timeout=10.0 to prevent database locked errors if main.py is currently writing
        async with aiosqlite.connect(db_path, timeout=10.0) as db:
            await db.execute("DELETE FROM active_tickets")
            await db.commit()
        print("State ledger wiped (active_tickets deleted).")
    except Exception as e:
        print(f"Failed to sanitize state ledger: {e}")

async def send_telegram_alert(bot_token: str, chat_id: str, message: str) -> None:
    """Dispatches a high priority alert via Telegram."""
    if not bot_token or not chat_id:
        print("Telegram credentials not found. Skipping Telegram alert.")
        return
        
    url: str = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload: Dict[str, str] = {
        "chat_id": chat_id,
        "text": message
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    print("Telegram alert sent successfully.")
                else:
                    text = await response.text()
                    print(f"Failed to send Telegram alert: {response.status} - {text}")
    except Exception as e:
        print(f"Exception during Telegram alert dispatch: {e}")

async def main() -> None:
    start_time: float = time.time()
    
    print("Operation: External Panic Switch Initiated")
    
    # Load environment variables
    load_dotenv()
    
    mt5_login_str: Optional[str] = os.getenv("MT5_LOGIN")
    mt5_password: Optional[str] = os.getenv("MT5_PASSWORD")
    mt5_server: Optional[str] = os.getenv("MT5_SERVER")
    mt5_terminal_path: Optional[str] = os.getenv("MT5_TERMINAL_PATH")
    
    magic_number_str: Optional[str] = os.getenv("MAGIC_NUMBER")
    telegram_bot_token: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = os.getenv("TELEGRAM_CHAT_ID")
    
    if not mt5_login_str or not mt5_password or not mt5_server:
        print("Error: MT5 credentials missing in .env")
        return
        
    try:
        mt5_login: int = int(mt5_login_str)
    except ValueError:
        print("Error: MT5_LOGIN must be an integer.")
        return
        
    try:
        magic_number: int = int(magic_number_str) if magic_number_str else 777999
    except ValueError:
        print("Error: MAGIC_NUMBER must be an integer.")
        return

    # Initialize MT5
    print(f"Initializing MT5 (Login: {mt5_login}, Server: {mt5_server})...")
    init_kwargs: Dict[str, Any] = {
        "login": mt5_login,
        "password": mt5_password,
        "server": mt5_server
    }
    if mt5_terminal_path:
        init_kwargs["path"] = mt5_terminal_path
        
    init_result: bool = await asyncio.to_thread(mt5.initialize, **init_kwargs)
    if not init_result:
        print("Error: Failed to initialize MT5")
        return
        
    try:
        # TASK 1: INDEPENDENT MT5 FLATTENING
        await flatten_book(magic_number)
        
        # TASK 2: STATE LEDGER SANITIZATION
        db_path: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aurexis_state.db")
        await sanitize_state_ledger(db_path)
        
        # TASK 3: FATAL OVERRIDE TELEMETRY
        alert_message: str = "CRITICAL: PANIC BUTTON ACTIVATED. ALL POSITIONS CLOSED. LEDGER WIPED."
        await send_telegram_alert(telegram_bot_token or "", telegram_chat_id or "", alert_message)
    finally:
        await asyncio.to_thread(mt5.shutdown)
    
    end_time: float = time.time()
    execution_time: float = end_time - start_time
    print(f"Physical execution time taken to clear the portfolio: {execution_time:.4f} seconds")

if __name__ == "__main__":
    asyncio.run(main())
