import asyncio
import aiosqlite
import time
import os
import MetaTrader5 as mt5
from src.core.event_bus import EventBus, SignalEvent, OrderEvent, MacroUpdateEvent, StructuralTrendEvent, TickEvent
from src.core.config import setup_logger, run_mt5_task; import src.core.config as config

logger = setup_logger("quant_lake")

class QuantDataHarvester:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.db_path = "db/aurexis_quant_lake.db"
        
        # Feature Caches
        self._last_dxy = 0.0
        self._last_us10y = 0.0
        self._last_m15_atr = 0.0
        self._last_spread_points = 0.0
        
        # Pending signals mapping: key = f"{cycle_id}_{direction}_{order_type}"
        self._pending_signals = {}
        
        # Mapping ticket -> record_id for asynchronous updating
        self._ticket_to_record_id = {}

        self.event_bus.subscribe(MacroUpdateEvent, self._handle_macro)
        self.event_bus.subscribe(StructuralTrendEvent, self._handle_structure)
        self.event_bus.subscribe(SignalEvent, self._handle_signal)
        self.event_bus.subscribe(OrderEvent, self._handle_order)
        
    async def perform_weekend_maintenance(self) -> float:
        import os
        logger.info(f"Executing Weekend SQLite Maintenance on {self.db_path}...")
        
        initial_size = 0.0
        if os.path.exists(self.db_path):
            initial_size = os.path.getsize(self.db_path)
            
        async with aiosqlite.connect(self.db_path, isolation_level=None) as db:
            async with db.execute("PRAGMA wal_checkpoint(TRUNCATE);"):
                pass
            async with db.execute("VACUUM;"):
                pass
            
        final_size = 0.0
        if os.path.exists(self.db_path):
            final_size = os.path.getsize(self.db_path)
            
        freed_mb = max(0.0, (initial_size - final_size) / (1024 * 1024))
        logger.info(f"Maintenance complete for {self.db_path}. Freed: {freed_mb:.2f} MB.")
        return freed_mb

    async def initialize(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS feature_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket INTEGER,
                    timestamp REAL,
                    cycle_id INTEGER,
                    direction TEXT,
                    order_type TEXT,
                    conviction_score REAL,
                    dxy_val REAL,
                    us10y_val REAL,
                    m15_atr REAL,
                    spread_points REAL,
                    signal_price REAL,
                    execution_price REAL,
                    slippage_points REAL,
                    result_pnl REAL
                )
            """)
            await db.commit()
        logger.info(f"Quant Data Lake initialized at {self.db_path} (WAL mode).")

    async def _handle_macro(self, event: MacroUpdateEvent):
        if not event.is_historical:
            self._last_dxy = event.dxy
            self._last_us10y = event.us10y
            
    async def _handle_structure(self, event: StructuralTrendEvent):
        self._last_m15_atr = getattr(event, "m15_atr", 0.0)

    async def _handle_signal(self, event: SignalEvent):
        if event.direction not in ["BUY", "SELL"]:
            return
            
        point = 0.00001
        try:
            # Snapshot spread precisely at signal time
            tick = await run_mt5_task(lambda: mt5.symbol_info_tick(config.TRADING_SYMBOL))
            symbol_info = await run_mt5_task(lambda: mt5.symbol_info(config.TRADING_SYMBOL))
            if tick and symbol_info:
                point = symbol_info.point
                self._last_spread_points = (tick.ask - tick.bid) / point
        except Exception:
            pass

        key = f"{event.cycle_id}_{event.direction}_{event.order_type}"
        self._pending_signals[key] = {
            "timestamp": time.time(),
            "cycle_id": event.cycle_id,
            "direction": event.direction,
            "order_type": event.order_type,
            "conviction_score": event.conviction,
            "dxy_val": self._last_dxy,
            "us10y_val": self._last_us10y,
            "m15_atr": self._last_m15_atr,
            "spread_points": self._last_spread_points,
            "signal_price": event.price
        }

    async def _handle_order(self, event: OrderEvent):
        # 1. Insert snapshot when order is FILLED
        if event.status == "FILLED" and event.direction in ["BUY", "SELL"]:
            key = f"{event.cycle_id}_{event.direction}_{event.order_type}"
            payload = self._pending_signals.pop(key, None)
            
            if not payload:
                payload = {
                    "timestamp": time.time(),
                    "cycle_id": event.cycle_id,
                    "direction": event.direction,
                    "order_type": event.order_type,
                    "conviction_score": 0.0,
                    "dxy_val": self._last_dxy,
                    "us10y_val": self._last_us10y,
                    "m15_atr": self._last_m15_atr,
                    "spread_points": self._last_spread_points,
                    "signal_price": event.price
                }
                
            execution_price = event.price
            
            point = 0.00001
            try:
                symbol_info = await run_mt5_task(lambda: mt5.symbol_info(event.symbol))
                if symbol_info:
                    point = symbol_info.point
            except Exception:
                pass
                
            slippage_points = abs(execution_price - payload["signal_price"]) / point
            
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('''
                    INSERT INTO feature_snapshots 
                    (ticket, timestamp, cycle_id, direction, order_type, conviction_score, 
                     dxy_val, us10y_val, m15_atr, spread_points, signal_price, execution_price, 
                     slippage_points, result_pnl)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event.ticket, payload["timestamp"], payload["cycle_id"], payload["direction"], 
                    payload["order_type"], payload["conviction_score"], payload["dxy_val"], 
                    payload["us10y_val"], payload["m15_atr"], payload["spread_points"], 
                    payload["signal_price"], execution_price, slippage_points, 0.0
                ))
                record_id = cursor.lastrowid
                await db.commit()
                self._ticket_to_record_id[event.ticket] = record_id
                logger.info(f"Quant Data Lake: Inserted Feature Snapshot for Ticket {event.ticket}")
                
        # 2. Update Result PnL when position is closed (MT5Bridge emits CLOSED_SYNC)
        elif event.direction == "CLOSED_SYNC" or event.status == "CLOSED_SYNC":
            record_id = self._ticket_to_record_id.pop(event.ticket, None)
            if record_id is not None:
                # event.price holds the net_pnl in MT5Bridge CLOSED_SYNC logic
                net_pnl = event.price
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute('''
                        UPDATE feature_snapshots
                        SET result_pnl = ?
                        WHERE id = ?
                    ''', (net_pnl, record_id))
                    await db.commit()
                    logger.info(f"Quant Data Lake: Updated record {record_id} with ML Label (PnL: {net_pnl:.2f})")
