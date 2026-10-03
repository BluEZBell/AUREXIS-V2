from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import asyncio
import json
import dataclasses
from typing import List
from src.core.event_bus import EventBus, ErrorEvent, OrderEvent, TickEvent, SignalEvent, MacroUpdateEvent, PositionsUpdateEvent, CommandEvent
import src.core.config as config

app = FastAPI(title="AUREXIS V2 Tactical Web")
templates = Jinja2Templates(directory="src/web/templates")
_event_bus: EventBus = None
_strategy = None
_latest_structural_trend = None
_latest_signal = None

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
                await asyncio.wait_for(connection.send_text(message), timeout=0.5)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

_latest_tick = None
_ui_account_state = {}

_latest_strategy_state = None

async def _broadcast_event(event):
    try:
        global _latest_structural_trend, _latest_signal, _latest_tick, _ui_account_state, _latest_strategy_state
        event_type = type(event).__name__
        if event_type == "StructuralTrendEvent":
            _latest_structural_trend = dataclasses.asdict(event)
        elif event_type == "SignalEvent":
            _latest_signal = dataclasses.asdict(event)
        elif event_type == "TickEvent":
            _latest_tick = dataclasses.asdict(event)
            return
        elif event_type == "PositionsUpdateEvent":
            _ui_account_state = dataclasses.asdict(event)
        elif event_type == "StrategyStateEvent":
            _latest_strategy_state = dataclasses.asdict(event)
            _latest_strategy_state["adx_m15"] = getattr(event, "adx_m15", 0.0)
            _latest_strategy_state["z_score"] = getattr(event, "z_score", 0.0)
            _latest_strategy_state["atr_m15"] = getattr(event, "atr_m15", 0.0)
            return
        elif event_type == "OrderEvent":
            if getattr(event, "status", "") == "CLOSED_SYNC" or getattr(event, "direction", "") == "MODIFY_SL":
                return
                
        if not manager.active_connections:
            return
        data = {
            "type": event_type,
            "data": dataclasses.asdict(event),
            "auto_sniper_enabled": getattr(_strategy, "auto_sniper", False) if _strategy else False
        }
        await manager.broadcast(json.dumps(_safe_serialize(data)))
    except Exception as e:
        logger.error(f"ERROR in _broadcast_event ({type(event).__name__}): {e}")

def inject_event_bus(bus: EventBus):
    global _event_bus
    _event_bus = bus
    if _event_bus:
        from src.core.event_bus import StrategyStateEvent
        _event_bus.subscribe(SignalEvent, _broadcast_event)
        _event_bus.subscribe(TickEvent, _broadcast_event)
        _event_bus.subscribe(MacroUpdateEvent, _broadcast_event)
        _event_bus.subscribe(ErrorEvent, _broadcast_event)
        _event_bus.subscribe(OrderEvent, _broadcast_event)
        _event_bus.subscribe(PositionsUpdateEvent, _broadcast_event)
        _event_bus.subscribe(StrategyStateEvent, _broadcast_event)
        
        from src.core.event_bus import StructuralTrendEvent, LogEvent
        _event_bus.subscribe(StructuralTrendEvent, _broadcast_event)
        _event_bus.subscribe(LogEvent, _broadcast_event)

@app.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})

@app.on_event("startup")
async def start_heartbeat():
    asyncio.create_task(heartbeat_loop())

import datetime
import logging
logger = logging.getLogger("app")

async def heartbeat_loop():
    while True:
        try:
            await asyncio.sleep(1)
            
            auto_sniper = getattr(_strategy, "auto_sniper", False) if _strategy else False
            
            h1_trend = "NEUTRAL"
            m15_trend = "NEUTRAL"
            adx = 0.0
            rsi = 50.0
            score = 50.0
            
            if _latest_structural_trend:
                h1_trend = _latest_structural_trend.get("h1_trend", "NEUTRAL")
                m15_trend = _latest_structural_trend.get("m15_trend", "NEUTRAL")
                adx = _latest_structural_trend.get("m15_adx", 0.0)
                rsi = _latest_structural_trend.get("m15_rsi", 50.0)
                
            if _latest_strategy_state:
                score = _latest_strategy_state.get("current_score", 50.0)
            elif _strategy:
                score = getattr(_strategy, "current_score", 50.0)
                
            gatekeeper_reason = "ACTIVE"
            if not auto_sniper:
                gatekeeper_reason = "PAUSED"
            elif _latest_strategy_state:
                if _latest_strategy_state.get("whipsaw_locked", False):
                    gatekeeper_reason = "WHIPSAW LOCKED"
                else:
                    state = _latest_strategy_state.get("cycle_state", "IDLE")
                    phase = _latest_strategy_state.get("swarm_type", "")
                    gatekeeper_reason = f"{state} {phase}".strip()
                
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            
            price_info = ""
            if _latest_tick:
                bid = _latest_tick.get("bid", 0.0)
                ask = _latest_tick.get("ask", 0.0)
                point = 0.01 if ask > 100 else 0.00001
                spread_pts = (ask - bid) / point if point else 0
                price_info = f" {bid:.2f} (Spread: {spread_pts:.0f} pts) |"
                
            msg = f"[{timestamp}] SCANNING GOLD{price_info} H1:{h1_trend} M15:{m15_trend} | ADX:{adx:.1f} RSI:{rsi:.1f} | Score:{score:.1f} -> {gatekeeper_reason}"
            
            if manager.active_connections:
                # Send LogEvent directly over WS to avoid queue congestion
                log_data = {
                    "type": "LogEvent",
                    "data": {"message": msg, "level": "INFO"}
                }
                await manager.broadcast(json.dumps(_safe_serialize(log_data)))
                
                sig = _latest_signal.copy() if _latest_signal else {}
                if _strategy:
                    sig["conviction"] = getattr(_strategy, "current_score", 50.0)
                
                state_data = {
                    "type": "UIStateUpdate",
                    "data": {
                        "latest_structural_trend": _latest_structural_trend,
                        "latest_signal": sig,
                        "account_state": _ui_account_state,
                        "latest_strategy_state": _latest_strategy_state,
                        "conviction_score": score
                    },
                    "auto_sniper_enabled": auto_sniper
                }
                await manager.broadcast(json.dumps(_safe_serialize(state_data)))
        except Exception as e:
            logger.error(f"Error in heartbeat_loop: {e}")
            await asyncio.sleep(1)

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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We don't just wait for receive_text, we also push state every 1s if needed
            # But the heartbeat_loop is already doing manager.broadcast() every 1s!
            # So here we just need to keep the connection open and receive commands.
            data = await websocket.receive_text()
            # process incoming WS data if any
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
        manager.disconnect(websocket)

class ActionRequest(BaseModel):
    action: str

@app.post("/api/tactical")
async def tactical_action(req: ActionRequest):
    if req.action == "FORCE_BUY":
        if _event_bus:
            await _event_bus.publish(SignalEvent(symbol=config.TRADING_SYMBOL, direction="BUY", strategy_id="MANUAL_FORCE", price=0.0, conviction=100.0, volume=0.0))
        return {"status": "Force Buy executed"}
    elif req.action == "FORCE_SELL":
        if _event_bus:
            await _event_bus.publish(SignalEvent(symbol=config.TRADING_SYMBOL, direction="SELL", strategy_id="MANUAL_FORCE", price=0.0, conviction=0.0, volume=0.0))
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
            
            async def force_sync():
                await asyncio.sleep(0.05)
                if manager.active_connections:
                    sig = _latest_signal.copy() if _latest_signal else {}
                    if _strategy:
                        sig["conviction"] = getattr(_strategy, "current_score", 50.0)
                    state_data = {
                        "type": "UIStateUpdate",
                        "data": {
                            "latest_structural_trend": _latest_structural_trend,
                            "latest_signal": sig
                        },
                        "auto_sniper_enabled": getattr(_strategy, "auto_sniper", False) if _strategy else False
                    }
                    await manager.broadcast(json.dumps(_safe_serialize(state_data)))
            asyncio.create_task(force_sync())
        return {"status": "Auto-Sniper toggled"}
    return {"status": "Unknown Action"}
