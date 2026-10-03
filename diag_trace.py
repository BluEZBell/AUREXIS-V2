import asyncio
import time
import MetaTrader5 as mt5
from src.core.event_bus import EventBus, CommandEvent
from src.execution.risk_manager import RiskManager
from src.execution.bridge import MT5Bridge
from src.data.macro_spies import MacroSpyNetwork
from src.strategy.alpha_harvester import AlphaHarvesterStrategy
import src.web.app as web_app
import logging

logging.basicConfig(level=logging.WARNING)

async def diag_trace():
    mt5.initialize()
    
    eb = EventBus()
    rm = RiskManager(eb, live_balance=1000.0)
    bridge = MT5Bridge(eb, rm)
    harvester = AlphaHarvesterStrategy(eb, rm)
    harvester.startup_time = 0.0
    harvester.auto_sniper = True
    spies = MacroSpyNetwork(eb)
    
    web_app.inject_event_bus(eb)
    web_app.inject_strategy(harvester)
    
    tasks = [
        asyncio.create_task(eb.process_events()),
        asyncio.create_task(bridge.start_position_broadcaster()),
        asyncio.create_task(bridge.start_tick_stream()),
        asyncio.create_task(bridge.start_structure_stream()),
        asyncio.create_task(spies.start())
    ]
    
    print("--- 15-SECOND DIAGNOSTIC TRACE STARTED ---")
    for i in range(1, 16):
        await asyncio.sleep(1.0)
        
        bid = 0.0
        ask = 0.0
        spread = 0.0
        if web_app._latest_tick:
            bid = web_app._latest_tick.get('bid', 0.0)
            ask = web_app._latest_tick.get('ask', 0.0)
            point = 0.01 if ask > 100 else 0.00001
            spread = (ask - bid) / point if point else 0
            
        h1 = "NEUTRAL"
        m15 = "NEUTRAL"
        adx = 0.0
        rsi = 50.0
        bear = True
        bull = True
        if web_app._latest_structural_trend:
            h1 = web_app._latest_structural_trend.get('h1_trend', 'NEUTRAL')
            m15 = web_app._latest_structural_trend.get('m15_trend', 'NEUTRAL')
            adx = web_app._latest_structural_trend.get('m15_adx', 0.0)
            rsi = web_app._latest_structural_trend.get('m15_rsi', 50.0)
            bear = web_app._latest_structural_trend.get('m15_bearish_candle', True)
            bull = web_app._latest_structural_trend.get('m15_bullish_candle', True)
            
        score = getattr(harvester, 'current_score', 50.0)
        
        pos_count = 0
        if web_app._ui_account_state and "positions" in web_app._ui_account_state:
            pos_count = len(web_app._ui_account_state["positions"])
            
        last_log = "None"
        
        print(f"Sec {i} | Price:{bid:.2f}/{ask:.2f} (Spread:{spread:.0f}) | H1:{h1} M15:{m15} | ADX:{adx:.1f} RSI:{rsi:.1f} | BearCandle:{bear} BullCandle:{bull} | Score:{score:.1f} | Positions:{pos_count} | LastLog:{last_log}")

    print("--- TRACE COMPLETED ---")
    
    for t in tasks:
        t.cancel()
    
    mt5.shutdown()

asyncio.run(diag_trace())
