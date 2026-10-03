from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import asyncio
import json
import dataclasses
import os
import glob
from typing import List, Dict, Any, Union
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from src.core.event_bus import EventBus, ErrorEvent, OrderEvent, TickEvent, SignalEvent, MacroUpdateEvent, PositionsUpdateEvent, CommandEvent
import src.core.config as config

app = FastAPI(title="AUREXIS V2 Tactical Web")
templates = Jinja2Templates(directory="src/web/templates")
_event_bus: EventBus = None
_strategy = None

# Global state to pack
_state = {
    "latest_structural_trend": None,
    "latest_signal": None,
    "latest_tick": None,
    "ui_account_state": None,
    "latest_strategy_state": None,
    "latest_macro": None
}

import queue
_event_queue = queue.Queue()

import logging

class WebSocketLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            _event_queue.put_nowait({
                "type": "LogEvent",
                "data": {"message": msg, "level": record.levelname}
            })
        except Exception:
            self.handleError(record)

def inject_strategy(strategy):
    global _strategy
    _strategy = strategy

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                # Still use wait_for to prevent slow clients from blocking
                await asyncio.wait_for(connection.send_text(message), timeout=0.5)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

import logging
logger = logging.getLogger("app")

async def _broadcast_event(event):
    """
    Subscribed to EventBus. 
    MUST be 100% non-blocking. Network I/O is strictly forbidden here.
    """
    try:
        global _state, _event_queue
        event_type = type(event).__name__
        
        # 1. Update State
        if event_type == "StructuralTrendEvent":
            _state["latest_structural_trend"] = dataclasses.asdict(event)
        elif event_type == "SignalEvent":
            _state["latest_signal"] = dataclasses.asdict(event)
        elif event_type == "TickEvent":
            _state["latest_tick"] = dataclasses.asdict(event)
        elif event_type == "PositionsUpdateEvent":
            _state["ui_account_state"] = dataclasses.asdict(event)
        elif event_type == "MacroUpdateEvent":
            _state["latest_macro"] = dataclasses.asdict(event)
        elif event_type == "StrategyStateEvent":
            st = dataclasses.asdict(event)
            st["adx_m15"] = getattr(event, "adx_m15", 0.0)
            st["z_score"] = getattr(event, "z_score", 0.0)
            st["atr_m15"] = getattr(event, "atr_m15", 0.0)
            _state["latest_strategy_state"] = st
            
        # 2. Queue Discrete Events (Logs, Errors, Orders)
        elif event_type in ["OrderEvent", "ErrorEvent", "LogEvent"]:
            if event_type == "OrderEvent" and (getattr(event, "status", "") == "CLOSED_SYNC" or getattr(event, "direction", "") == "MODIFY_SL"):
                return
            _event_queue.put_nowait({
                "type": event_type,
                "data": dataclasses.asdict(event)
            })
            
    except Exception as e:
        logger.error(f"ERROR in _broadcast_event ({type(event).__name__}): {e}")

def inject_event_bus(bus: EventBus):
    global _event_bus
    _event_bus = bus
    if _event_bus:
        from src.core.event_bus import StrategyStateEvent, StructuralTrendEvent, LogEvent
        # Subscribe to all relevant events
        for evt in [SignalEvent, TickEvent, MacroUpdateEvent, ErrorEvent, OrderEvent, PositionsUpdateEvent, StrategyStateEvent, StructuralTrendEvent, LogEvent]:
            _event_bus.subscribe(evt, _broadcast_event)

@app.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})

@app.on_event("startup")
async def start_heartbeat():
    asyncio.create_task(heartbeat_loop())

import datetime
async def heartbeat_loop():
    """
    Background task that periodically gathers state and events, packs them into JSON, 
    and broadcasts to all connected WebSockets.
    """
    global _event_queue
    while True:
        try:
            await asyncio.sleep(0.5)
            
            if not manager.active_connections:
                while not _event_queue.empty():
                    try:
                        _event_queue.get_nowait()
                    except queue.Empty:
                        break
                continue
                
            auto_sniper = getattr(_strategy, "auto_sniper", False) if _strategy else False
            
            # --- Generate the "SCANNING" Log Message (from previous terminal HUD logic) ---
            h1_trend = "NEUTRAL"
            m15_trend = "NEUTRAL"
            adx = "AWAITING_DATA"
            rsi = "AWAITING_DATA"
            score = "AWAITING_DATA"
            
            if _state["latest_structural_trend"]:
                h1_trend = _state["latest_structural_trend"].get("h1_trend", "NEUTRAL")
                m15_trend = _state["latest_structural_trend"].get("m15_trend", "NEUTRAL")
                adx = _state["latest_structural_trend"].get("m15_adx", "AWAITING_DATA")
                rsi = _state["latest_structural_trend"].get("m15_rsi", "AWAITING_DATA")
                
            if _state["latest_strategy_state"]:
                score = _state["latest_strategy_state"].get("current_score", "AWAITING_DATA")
            elif _strategy:
                score = getattr(_strategy, "current_score", "AWAITING_DATA")
                
            gatekeeper_reason = "ACTIVE"
            if not auto_sniper:
                gatekeeper_reason = "PAUSED"
            elif _state["latest_strategy_state"]:
                if _state["latest_strategy_state"].get("whipsaw_locked", False):
                    gatekeeper_reason = "WHIPSAW LOCKED"
                else:
                    state_cycle = _state["latest_strategy_state"].get("cycle_state", "IDLE")
                    phase = _state["latest_strategy_state"].get("swarm_type", "")
                    gatekeeper_reason = f"{state_cycle} {phase}".strip()
                
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            price_info = ""
            if _state["latest_tick"]:
                bid = _state["latest_tick"].get("bid", 0.0)
                ask = _state["latest_tick"].get("ask", 0.0)
                point = 0.01 if ask > 100 else 0.00001
                spread_pts = (ask - bid) / point if point else 0
                price_info = f" {bid:.2f} (Spread: {spread_pts:.0f} pts) |"
                
            def _fmt(val):
                if val == "AWAITING_DATA" or val is None:
                    return "AWAITING_DATA"
                try:
                    return f"{float(val):.1f}"
                except:
                    return str(val)

            msg = f"[{timestamp}] SCANNING GOLD{price_info} H1:{h1_trend} M15:{m15_trend} | ADX:{_fmt(adx)} RSI:{_fmt(rsi)} | Score:{_fmt(score)} -> {gatekeeper_reason}"
            
            # Pack synthetic log event
            _event_queue.put_nowait({
                "type": "LogEvent",
                "data": {"message": msg, "level": "INFO"}
            })
            
            # Enqueue Conviction Score in signal state for frontend
            sig = _state["latest_signal"].copy() if _state["latest_signal"] else {}
            if _strategy:
                sig["conviction"] = getattr(_strategy, "current_score", "AWAITING_DATA")
                
            # Extract accumulated events
            events_to_send = []
            while not _event_queue.empty():
                try:
                    events_to_send.append(_event_queue.get_nowait())
                except queue.Empty:
                    break
            
            payload = {
                "type": "StatePack",
                "state": {
                    "latest_structural_trend": _state["latest_structural_trend"],
                    "latest_signal": sig,
                    "account_state": _state["ui_account_state"],
                    "latest_strategy_state": _state["latest_strategy_state"],
                    "latest_macro": _state["latest_macro"],
                    "conviction_score": score,
                    "auto_sniper_enabled": auto_sniper
                },
                "events": events_to_send
            }
            
            await manager.broadcast(json.dumps(_safe_serialize(payload)))
            
        except Exception as e:
            logger.error(f"Error in heartbeat_loop: {e}")
            await asyncio.sleep(0.5)

import numpy as np

def _safe_serialize(obj):
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_safe_serialize(v) for v in obj]
    elif isinstance(obj, (np.floating, float)):
        return float(obj)
    elif isinstance(obj, (np.integer, int)):
        return int(obj)
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
        manager.disconnect(websocket)

class ActionRequest(BaseModel):
    action: str

@app.get("/api/tearsheet", response_class=Response)
async def get_tearsheet() -> Response:
    def _read() -> Union[Dict[str, Any], None]:
        json_files = glob.glob("reports/tearsheet_*.json")
        if json_files:
            latest_file = max(json_files, key=os.path.getmtime)
            with open(latest_file, "r", encoding="utf-8") as f:
                return json.load(f)
                
        files = glob.glob("reports/tearsheet_*.md")
        if not files:
            return None
        latest_file = max(files, key=os.path.getmtime)
        with open(latest_file, "r", encoding="utf-8") as f:
            return {"markdown": f.read()}
            
    try:
        content = await asyncio.to_thread(_read)
        if content is None:
            return JSONResponse(status_code=404, content={"error": "EOD reports not yet generated"})
        return JSONResponse(content=content)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/tuner", response_class=Response)
async def get_tuner() -> Response:
    def _read() -> Union[Dict[str, Any], None]:
        tuner_file = "reports/alpha_tuner.json"
        if not os.path.exists(tuner_file):
            return None
        with open(tuner_file, "r", encoding="utf-8") as f:
            return json.load(f)
            
    try:
        content: Union[Dict[str, Any], None] = await asyncio.to_thread(_read)
        if content is None:
            return JSONResponse(status_code=404, content={"error": "EOD reports not yet generated"})
        return JSONResponse(content=content)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/command")
async def command_endpoint(req: ActionRequest):
    if _event_bus:
        await _event_bus.publish(CommandEvent(action=req.action))
        if req.action == "FORCE_BUY":
            sig = SignalEvent(symbol=config.TRADING_SYMBOL, direction="BUY", strategy_id="MANUAL_FORCE", price=0.0, conviction=100.0, volume=0.0, cycle_id=0, order_type="MANUAL", regime="MANUAL", mtf_volume_confirmed=False)
            await _event_bus.publish(sig)
        elif req.action == "FORCE_SELL":
            sig = SignalEvent(symbol=config.TRADING_SYMBOL, direction="SELL", strategy_id="MANUAL_FORCE", price=0.0, conviction=100.0, volume=0.0, cycle_id=0, order_type="MANUAL", regime="MANUAL", mtf_volume_confirmed=False)
            await _event_bus.publish(sig)
    return {"status": "success", "message": "Command injected", "action": req.action}

@app.post("/api/tactical")
async def tactical_action(req: ActionRequest):
    if req.action == "FORCE_BUY":
        if _event_bus:
            sig = SignalEvent(symbol=config.TRADING_SYMBOL, direction="BUY", strategy_id="MANUAL_FORCE", price=0.0, conviction=100.0, volume=0.0, cycle_id=0, order_type="MANUAL", regime="MANUAL", mtf_volume_confirmed=False)
            await _event_bus.publish(sig)
        return {"status": "Force Buy executed"}
    elif req.action == "FORCE_SELL":
        if _event_bus:
            sig = SignalEvent(symbol=config.TRADING_SYMBOL, direction="SELL", strategy_id="MANUAL_FORCE", price=0.0, conviction=100.0, volume=0.0, cycle_id=0, order_type="MANUAL", regime="MANUAL", mtf_volume_confirmed=False)
            await _event_bus.publish(sig)
        return {"status": "Force Sell executed"}
    elif req.action == "HARVEST_ALL":
        if _event_bus:
            await _event_bus.publish(OrderEvent(ticket=0, symbol="ALL", direction="HARVEST_ALL", volume=0.0, price=0.0, status="REQUEST"))
        return {"status": "Harvest All triggered"}
    elif req.action == "CHOP_50":
        if _event_bus:
            await _event_bus.publish(OrderEvent(ticket=0, symbol="ALL", direction="CHOP_50", volume=0.0, price=0.0, status="REQUEST"))
        return {"status": "Chop 50% triggered"}
    elif req.action == "PANIC_HALT":
        if _event_bus:
            await _event_bus.publish(ErrorEvent("Web UI", "TACTICAL PANIC HALT INITIATED", critical=True))
        return {"status": "PANIC HALT triggered"}
    elif req.action == "TOGGLE_AUTO_SNIPER":
        if _event_bus:
            await _event_bus.publish(CommandEvent(action="TOGGLE_AUTO_SNIPER"))
        return {"status": "Auto-Sniper toggled"}
    return {"status": "Unknown Action"}
