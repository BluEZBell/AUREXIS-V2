import asyncio
import MetaTrader5 as mt5
from src.core.event_bus import EventBus, MacroUpdateEvent, ErrorEvent
from src.core.config import setup_logger, run_mt5_task

logger = setup_logger("macro_spies")

def resolve_and_select_symbol(base_symbol: str) -> str:
    candidates = [base_symbol]
    if base_symbol == "XAUUSD":
        candidates = ["XAUUSD", "GOLD", "GOLD#", "GOLDm", "XAUUSDm", "GOLDmicro"]
    elif base_symbol == "XAGUSD":
        candidates = ["XAGUSD", "SILVER", "SILVER#", "XAGUSDm"]
    elif base_symbol == "DXY":
        candidates = ["DXY", "USDX", "USDXCash", "USXCash"]
        
    for cand in candidates:
        mt5.symbol_select(cand, True)
        if mt5.symbol_info(cand) is not None and mt5.symbol_info_tick(cand) is not None:
            return cand
                    
    return base_symbol

class MacroSpyNetwork:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.spies = {
            "DXY": ['USDXCash', 'USXCash', 'USDX', 'USX', 'DXY'],
            "EURUSD": ['EURUSD', 'EURUSD.p', 'EURUSD.c', 'EURUSD_micro'],
            "US10Y": ['US10Cash', 'US10YCash', 'US10YR', 'US10Y', 'TNOTE'],
            "USDJPY": ['USDJPY', 'USDJPY#', 'USDJPY.d', 'USDJPYm'],
            "VIX": ['VOLXCash', 'VIXCash', 'VOLX', 'VIX'],
            "US500": ['US500Cash', 'US500', 'SPX500'],
            "XAGUSD": ['SILVER', 'XAGUSD', 'SILVER#'],
            "USDCNH": ['USDCNH', 'USDCNH#'],
            "USOIL": ['OILCash', 'WTI_Oil', 'WTI', 'USOIL', 'BRENTCash', 'BRENT']
        }
        self.resolved_symbols = {}
        self.missing_logged = set()
        self._running = False

    async def _resolve_symbol(self, key: str) -> str:
        if key in self.resolved_symbols:
            return self.resolved_symbols[key]
        
        def _resolve():
            candidates = self.spies.get(key, [key])
            for c in candidates:
                res = resolve_and_select_symbol(c)
                if mt5.symbol_info(res) is not None:
                    return res
            return resolve_and_select_symbol(key)
            
        resolved = await run_mt5_task(_resolve)
        self.resolved_symbols[key] = resolved
        return resolved

    async def fetch_tick(self, key: str) -> float:
        symbol = await self._resolve_symbol(key)
        if not symbol:
            if key not in self.missing_logged:
                logger.warning(f"MacroSpy: Symbol {key} unavailable or neutral baseline returned.")
                self.missing_logged.add(key)
            return 0.0
            
        def _get_tick(s=symbol):
            try:
                tick = mt5.symbol_info_tick(s)
                if tick is None:
                    return 0.0
                return tick.bid
            except Exception as e:
                logger.error(f"Spy Error in _get_tick for {s}: {e}")
                return 0.0
        
        try:
            bid = await run_mt5_task(_get_tick)
            if bid == 0.0:
                if key not in self.missing_logged:
                    logger.warning(f"MacroSpy: Symbol {symbol} unavailable or neutral baseline returned.")
                    self.missing_logged.add(key)
            return bid
        except Exception as e:
            if key not in self.missing_logged:
                logger.warning(f"MacroSpy: Failed to fetch {symbol}: {e}")
                self.missing_logged.add(key)
            return 0.0

    async def start(self):
        self._running = True
        logger.info("Macro Spy Network started.")
        
        def _resolve_all():
            for key in ["DXY", "EURUSD", "US10Y", "USDJPY", "VIX", "US500", "XAGUSD", "USDCNH", "USOIL"]:
                if key not in self.resolved_symbols:
                    candidates = self.spies.get(key, [key])
                    resolved = None
                    for c in candidates:
                        res = resolve_and_select_symbol(c)
                        if mt5.symbol_info(res) is not None:
                            resolved = res
                            break
                    if resolved is None:
                        resolved = resolve_and_select_symbol(key)
                    self.resolved_symbols[key] = resolved
                    
        await run_mt5_task(_resolve_all)
        
        def _prewarm_history():
            import time
            current_time = time.time()
            historical_events = []
            
            # Fetch M1 candles for all resolved symbols up to 16 bars ago
            symbol_rates = {}
            for key, sym in self.resolved_symbols.items():
                rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 16)
                if rates is not None and len(rates) > 0:
                    symbol_rates[key] = rates
                else:
                    symbol_rates[key] = []
                    
            # Loop through 16 historical minutes (oldest to newest)
            for i in range(16):
                vals = {}
                timestamp = current_time - (15 - i) * 60.0
                for key in ["DXY", "EURUSD", "US10Y", "USDJPY", "VIX", "US500", "XAGUSD", "USDCNH", "USOIL"]:
                    rates = symbol_rates.get(key, [])
                    if len(rates) > i:
                        vals[key] = float(rates[i]['close'])
                    else:
                        vals[key] = 0.0
                historical_events.append(MacroUpdateEvent(
                    dxy=vals["DXY"],
                    us10y=vals["US10Y"],
                    usdjpy=vals["USDJPY"],
                    vix=vals["VIX"],
                    xagusd=vals["XAGUSD"],
                    usdcnh=vals["USDCNH"],
                    usoil=vals["USOIL"],
                    eurusd_val=vals["EURUSD"],
                    us500_val=vals["US500"],
                    is_historical=True,
                    timestamp=timestamp
                ))
            return historical_events
            
        hist_events = await run_mt5_task(_prewarm_history)
        for ev in hist_events:
            await self.event_bus.publish(ev)
            
        logger.info("Macro Spy Network history pre-warmed.")
        
        while self._running:
            try:
                # Explicit concurrent fetching with named mapping to eliminate any index swapping bugs
                dxy_val, eurusd_val, us10y_val, usdjpy_val, vix_val, us500_val, xagusd_val, usdcnh_val, usoil_val = await asyncio.gather(
                    self.fetch_tick("DXY"),
                    self.fetch_tick("EURUSD"),
                    self.fetch_tick("US10Y"),
                    self.fetch_tick("USDJPY"),
                    self.fetch_tick("VIX"),
                    self.fetch_tick("US500"),
                    self.fetch_tick("XAGUSD"),
                    self.fetch_tick("USDCNH"),
                    self.fetch_tick("USOIL")
                )
                
                event = MacroUpdateEvent(
                    dxy=dxy_val,
                    us10y=us10y_val,
                    usdjpy=usdjpy_val,
                    vix=vix_val,
                    xagusd=xagusd_val,
                    usdcnh=usdcnh_val,
                    usoil=usoil_val,
                    eurusd_val=eurusd_val,
                    us500_val=us500_val
                )
                await self.event_bus.publish(event)
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                self._running = False
                break
            except Exception as e:
                logger.exception("Loop Error in MacroSpyNetwork")
                await asyncio.sleep(1.0)
                
    def stop(self):
        self._running = False
