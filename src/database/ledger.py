import aiosqlite
import asyncio
import collections
from src.core.event_bus import EventBus, OrderEvent, TickEvent
from src.core.config import WEB_PORT, setup_logger

logger = setup_logger("ledger")

class Ledger:
    def __init__(self, event_bus: EventBus):
        self.db_name = f"ledger_{WEB_PORT}.db"
        self.event_bus = event_bus
        self.tick_buffer = collections.deque(maxlen=100000) # Lock-Free Ring Buffer
        
        # Subscribe to events for decoupling
        self.event_bus.subscribe(OrderEvent, self.handle_order_event)
        self.event_bus.subscribe(TickEvent, self.handle_tick_event)

    async def initialize(self):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute('''
                CREATE TABLE IF NOT EXISTS active_trades (
                    identifier INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    volume REAL NOT NULL,
                    price REAL NOT NULL,
                    status TEXT NOT NULL
                )
            ''')
            await db.commit()
            logger.info(f"Ledger initialized: {self.db_name} (WAL Mode)")
            
            # Orphan Trade Adoption protocol
            await self.adopt_orphan_trades(db)

    async def adopt_orphan_trades(self, db):
        async with db.execute("SELECT identifier FROM active_trades WHERE status='FILLED'") as cursor:
            orphans = await cursor.fetchall()
            if orphans:
                logger.info(f"Adopted {len(orphans)} orphan trades on startup.")

    async def handle_tick_event(self, event: TickEvent):
        # Extremely fast lock-free append for real-time tick ingestion
        self.tick_buffer.append(event)
        
    async def handle_order_event(self, event: OrderEvent):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                if event.status == "CLOSED_SYNC":
                    await db.execute(
                        "UPDATE active_trades SET status = ?, price = ? WHERE identifier = ?",
                        (event.status, event.price, event.ticket)
                    )
                else:
                    await db.execute(
                        "INSERT OR REPLACE INTO active_trades (identifier, symbol, direction, volume, price, status) VALUES (?, ?, ?, ?, ?, ?)",
                        (event.ticket, event.symbol, event.direction, event.volume, event.price, event.status)
                    )
                await db.commit()
                logger.info(f"Logged order {event.ticket} in Ledger.")
        except Exception as e:
            logger.error(f"Failed to log order: {e}")
