import asyncio
import logging
import json
import dataclasses
import datetime
import os
import glob
import mimetypes
from pathlib import Path
from typing import Any, Dict, Optional, Set
from aiohttp import web

# Enforce proper MIME types for static assets (bypasses Windows Registry issues)
mimetypes.add_type('text/html', '.html')
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('application/json', '.json')

logger = logging.getLogger("telemetry_server")

class TelemetryServer:
    def __init__(self, risk_manager: Any, tick_sentinel: Any, alpha_scorer: Optional[Any], telemetry_state: Optional[Any], event_bus: Optional[Any] = None) -> None:
        self.risk_manager = risk_manager
        self.tick_sentinel = tick_sentinel
        self.alpha_scorer = alpha_scorer
        self.telemetry_state = telemetry_state
        self.event_bus = event_bus
        self.strategy = None
        
        self.app: web.Application = web.Application()
        
        # Dynamically resolve absolute paths
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        self.frontend_dir = os.path.join(project_root, 'src', 'web', 'templates')
        self.static_dir = os.path.join(project_root, 'src', 'web', 'static')
        
        # Ensure static directory exists
        os.makedirs(self.static_dir, exist_ok=True)
        
        # UI & WebSocket Routes
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_static('/static', self.static_dir)
        self.app.router.add_get('/status', self.handle_status)
        self.app.router.add_get('/ws', self.handle_websocket)
        self.app.router.add_get('/ws/telemetry', self.handle_websocket)
        
        # Tactical API Routes
        self.app.router.add_post('/api/tactical', self.handle_api_tactical)
        self.app.router.add_post('/api/command', self.handle_api_tactical)
        self.app.router.add_post('/api/telegram-config', self.handle_telegram_config)
        
        # EOD Report Routes
        self.app.router.add_get('/api/tearsheet', self.handle_api_tearsheet)
        self.app.router.add_get('/api/tuner', self.handle_api_tuner)
        
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        
        self.active_websockets: Set[web.WebSocketResponse] = set()
        
        # State cache for UI logs
        self._latest_structural_trend: Dict[str, Any] = {}
        self._latest_strategy_state: Dict[str, Any] = {}
        self._latest_signal: Dict[str, Any] = {}
        self._cached_state: Dict[str, Any] = {}

        if self.event_bus:
            self._subscribe_events()

    def _subscribe_events(self) -> None:
        try:
            from src.core.event_bus import (
                TickEvent, PositionsUpdateEvent, StrategyStateEvent, 
                LogEvent, OrderEvent, SignalEvent, StructuralTrendEvent, 
                MacroUpdateEvent, ErrorEvent
            )
            events = [TickEvent, PositionsUpdateEvent, StrategyStateEvent, 
                      LogEvent, OrderEvent, SignalEvent, StructuralTrendEvent, 
                      MacroUpdateEvent, ErrorEvent]
            for event_type in events:
                self.event_bus.subscribe(event_type, self._on_event)
        except ImportError as e:
            logger.warning(f"Could not import events for telemetry server: {e}")

    async def handle_index(self, request: web.Request) -> web.Response:
        index_path = os.path.join(self.frontend_dir, 'index.html')
        if os.path.exists(index_path):
            resp = web.FileResponse(index_path)
            resp.content_type = 'text/html'
            return resp
        return web.Response(text="UI Assets Not Found", status=404)

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.active_websockets.add(ws)
        
        msg_queue = asyncio.Queue()
        setattr(ws, 'msg_queue', msg_queue)
        
        import json
        if self._cached_state:
            initial_pack = {
                "type": "StatePack",
                "state": self._cached_state
            }
            msg_queue.put_nowait(json.dumps(initial_pack, default=self._json_default))
        
        async def writer():
            try:
                while not ws.closed:
                    msg = await msg_queue.get()
                    await ws.send_str(msg)
            except Exception:
                pass

        writer_task = asyncio.create_task(writer())

        logger.info(f"WebSocket client connected. Active: {len(self.active_websockets)}")
        try:
            async for msg in ws:
                pass  # Ignore incoming messages, keeping connection open
        finally:
            writer_task.cancel()
            self.active_websockets.discard(ws)
            logger.info(f"WebSocket client disconnected. Active: {len(self.active_websockets)}")
        return ws
        
    async def _broadcast(self, msg: str) -> None:
        if not self.active_websockets:
            return
        # Broadcast fire-and-forget to all active websockets
        for ws in list(self.active_websockets):
            if not ws.closed and hasattr(ws, 'msg_queue'):
                try:
                    ws.msg_queue.put_nowait(msg)
                except Exception:
                    self.active_websockets.discard(ws)

    def _json_default(self, obj: Any) -> Any:
        try:
            import numpy as np
            if isinstance(obj, (np.floating, float)):
                return float(obj)
            if isinstance(obj, (np.integer, int)):
                return int(obj)
            if isinstance(obj, (np.bool_, bool)):
                return bool(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        return str(obj)

    async def _on_event(self, event: Any) -> None:
        event_type = type(event).__name__
        try:
            data_dict = dataclasses.asdict(event) if dataclasses.is_dataclass(event) else getattr(event, "__dict__", {})
        except Exception:
            data_dict = {}

        payloads_to_send = []

        if event_type in ("PositionsUpdateEvent", "StrategyStateEvent", "StructuralTrendEvent", "MacroUpdateEvent", "SignalEvent"):
            state: Dict[str, Any] = {}
            if event_type == "PositionsUpdateEvent":
                state["account_state"] = data_dict
            elif event_type == "StrategyStateEvent":
                self._latest_strategy_state = data_dict
                state["latest_strategy_state"] = data_dict
                if "current_score" in data_dict:
                    state["conviction_score"] = data_dict["current_score"]
                if hasattr(event, "adx_m15"):
                    state["latest_strategy_state"]["adx_m15"] = getattr(event, "adx_m15", 0.0)
                if hasattr(event, "z_score"):
                    state["latest_strategy_state"]["z_score"] = getattr(event, "z_score", 0.0)
                if hasattr(event, "atr_m15"):
                    state["latest_strategy_state"]["atr_m15"] = getattr(event, "atr_m15", 0.0)
            elif event_type == "StructuralTrendEvent":
                self._latest_structural_trend = data_dict
                state["latest_structural_trend"] = data_dict
            elif event_type == "MacroUpdateEvent":
                state["latest_macro"] = data_dict
            elif event_type == "SignalEvent":
                self._latest_signal = data_dict
                state["latest_signal"] = data_dict

            if self.strategy:
                state["auto_sniper_enabled"] = getattr(self.strategy, "auto_sniper", False)
                
            self._cached_state.update(state)

            pack = {
                "type": "StatePack",
                "state": state
            }
            if event_type == "SignalEvent":
                pack["events"] = [{"type": "SignalEvent", "data": data_dict}]
            
            payloads_to_send.append(pack)

        elif event_type in ("OrderEvent", "ErrorEvent", "LogEvent"):
            payloads_to_send.append({
                "type": event_type,
                "data": data_dict
            })
            
        elif event_type == "TickEvent":
            h1_trend = self._latest_structural_trend.get("h1_trend", "NEUTRAL")
            m15_trend = self._latest_structural_trend.get("m15_trend", "NEUTRAL")
            adx = self._latest_structural_trend.get("m15_adx", "AWAITING_DATA")
            rsi = self._latest_structural_trend.get("m15_rsi", "AWAITING_DATA")
            
            score = "AWAITING_DATA"
            if self._latest_strategy_state:
                score = self._latest_strategy_state.get("current_score", "AWAITING_DATA")
            elif self.strategy:
                score = getattr(self.strategy, "current_score", "AWAITING_DATA")
            
            gatekeeper_reason = "ACTIVE"
            auto_sniper = getattr(self.strategy, "auto_sniper", False) if self.strategy else False
            if not auto_sniper:
                gatekeeper_reason = "PAUSED"
            elif self._latest_strategy_state.get("whipsaw_locked", False):
                gatekeeper_reason = "WHIPSAW LOCKED"
            else:
                state_val = self._latest_strategy_state.get("cycle_state", "IDLE")
                phase_val = self._latest_strategy_state.get("swarm_type", "")
                gatekeeper_reason = f"{state_val} {phase_val}".strip()

            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            bid = data_dict.get("bid", 0.0)
            ask = data_dict.get("ask", 0.0)
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
            
            logger.info(msg)
            
            payloads_to_send.append({
                "type": "LogEvent",
                "data": {"message": msg, "level": "INFO"}
            })

        if not self.active_websockets:
            return

        for payload in payloads_to_send:
            try:
                json_str = json.dumps(payload, default=self._json_default)
                asyncio.create_task(self._broadcast(json_str))
            except Exception as e:
                logger.error(f"Error serializing event {event_type}: {e}")


    async def handle_telegram_config(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            bot_token = data.get('bot_token', '').strip()
            chat_id = data.get('chat_id', '').strip()
            
            if not bot_token or not chat_id:
                return web.json_response({"error": "Missing bot_token or chat_id"}, status=400)
                
            import dotenv
            import asyncio
            import src.core.config as config
            
            # Update memory
            config.TELEGRAM_BOT_TOKEN = bot_token
            config.TELEGRAM_CHAT_ID = chat_id
            
            # Persist to .env asynchronously
            def _save_env():
                dotenv.set_key('.env', 'TELEGRAM_BOT_TOKEN', bot_token)
                dotenv.set_key('.env', 'TELEGRAM_CHAT_ID', chat_id)
            await asyncio.to_thread(_save_env)
            
            # Broadcast test message asynchronously
            async def _send_test():
                try:
                    from src.core.broadcaster import TelegramBroadcaster
                    broadcaster = TelegramBroadcaster(bot_token=bot_token, chat_id=chat_id)
                    await broadcaster.start()
                    await broadcaster.broadcast("🟢 [AUREXIS V2] Telegram link established. HFT Engine standing by.")
                    await asyncio.sleep(2) # Give it time to flush
                    await broadcaster.stop()
                except Exception as e:
                    logger.error(f"Failed to send Telegram test message: {e}")
                    
            asyncio.create_task(_send_test())
            
            return web.json_response({"status": "Success"})
        except Exception as e:
            logger.error(f"Error in handle_telegram_config: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_api_tactical(self, request: web.Request) -> web.Response:
        if not self.event_bus:
            return web.json_response({"status": "No event bus"}, status=500)
            
        data = await request.json()
        action = data.get("action", "")
        
        try:
            from src.core.event_bus import SignalEvent, OrderEvent, ErrorEvent, CommandEvent
            from src.core import config
            
            if action == "FORCE_BUY":
                await self.event_bus.publish(SignalEvent(symbol=config.TRADING_SYMBOL, direction="BUY", strategy_id="MANUAL_FORCE", price=0.0, conviction=100.0, volume=0.01))
            elif action == "FORCE_SELL":
                await self.event_bus.publish(SignalEvent(symbol=config.TRADING_SYMBOL, direction="SELL", strategy_id="MANUAL_FORCE", price=0.0, conviction=100.0, volume=0.01))
            elif action == "HARVEST_ALL":
                await self.event_bus.publish(OrderEvent(ticket=0, symbol="ALL", direction="HARVEST_ALL", volume=0.0, price=0.0, status="REQUEST"))
            elif action == "CHOP_50":
                await self.event_bus.publish(OrderEvent(ticket=0, symbol="ALL", direction="CHOP_50", volume=0.0, price=0.0, status="REQUEST"))
            elif action == "PANIC_HALT":
                await self.event_bus.publish(OrderEvent(ticket=0, symbol="ALL", direction="PANIC_HALT", volume=0.0, price=0.0, status="REQUEST"))
                await self.event_bus.publish(ErrorEvent("Web UI", "TACTICAL PANIC HALT INITIATED", critical=True))
            elif action == "TOGGLE_AUTO_SNIPER":
                await self.event_bus.publish(CommandEvent(action="TOGGLE_AUTO_SNIPER"))
                
            return web.json_response({"status": f"{action} executed"})
        except Exception as e:
            logger.error(f"API Tactical error: {e}")
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def handle_api_tearsheet(self, request: web.Request) -> web.Response:
        def _read():
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
                return web.json_response({"error": "EOD reports not yet generated"}, status=404)
            return web.json_response(content)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_api_tuner(self, request: web.Request) -> web.Response:
        def _read():
            tuner_file = "reports/alpha_tuner.json"
            if not os.path.exists(tuner_file):
                return None
            with open(tuner_file, "r", encoding="utf-8") as f:
                return json.load(f)
        try:
            content = await asyncio.to_thread(_read)
            if content is None:
                return web.json_response({"error": "EOD reports not yet generated"}, status=404)
            return web.json_response(content)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_status(self, request: web.Request) -> web.Response:
        try:
            live_equity: float = float(getattr(self.risk_manager, 'live_equity', getattr(self.risk_manager, 'session_start_equity', 0.0)))
            session_start: float = float(getattr(self.risk_manager, 'session_start_equity', 0.0))
            multiplier: float = float(getattr(self.risk_manager, 'target_multiplier', 2.0))
            next_target: float = session_start * multiplier

            active_tickets: int = len(getattr(self.tick_sentinel, '_positions', {}))
            risk_quota_state: str = "ACTIVE" if active_tickets > 0 else "IDLE"

            velocity: float = float(getattr(self.alpha_scorer, 'current_velocity', 0.0)) if self.alpha_scorer else 0.0
            lookback: int = 7
            if velocity > 10.0:
                lookback = 3
            elif velocity >= 3.0:
                lookback = 5

            latency: float = float(getattr(self.telemetry_state, 'processing_latency_ms', 0.0)) if self.telemetry_state else 0.0

            payload: Dict[str, Any] = {
                "live_equity": live_equity,
                "next_milestone_target": next_target,
                "active_ticket_count": active_tickets,
                "risk_quota_state": risk_quota_state,
                "current_tick_velocity": velocity,
                "active_lookback_threshold": lookback,
                "last_execution_latency_ms": latency
            }
            return web.json_response(payload)
        except Exception as e:
            logger.error(f"Telemetry API endpoint error: {e}")
            return web.json_response({"error": "Internal server error"}, status=500)

    async def start(self) -> None:
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, '0.0.0.0', 8080)
            await self.site.start()
            logger.info("INFO | Telemetry API running at http://localhost:8080/status")
        except Exception as e:
            logger.warning(f"Telemetry API Server failed to bind to 0.0.0.0:8080 or start: {e}. Bypassing startup.")

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()
