import aiosqlite
import asyncio
from typing import Dict, Any, List
import logging

logger = logging.getLogger("state_ledger")

class StateLedger:
    def __init__(self, db_path: str = "aurexis_state.db") -> None:
        self.db_path: str = db_path
        self._background_tasks: set[asyncio.Task[Any]] = set()

    def _fire_and_forget(self, coro: Any) -> None:
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def initialize(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS active_tickets (
                    ticket_id INTEGER PRIMARY KEY,
                    magic_number INTEGER,
                    virtual_sl REAL,
                    virtual_tp REAL,
                    risk_recycled BOOLEAN
                )
            ''')
            await db.commit()

    async def sync(self) -> None:
        await self.initialize()

    def update_ticket_state(self, ticket_id: int, magic_number: int, virtual_sl: float, virtual_tp: float, risk_recycled: bool) -> None:
        self._fire_and_forget(self._update_ticket_state_async(ticket_id, magic_number, virtual_sl, virtual_tp, risk_recycled))

    async def _update_ticket_state_async(self, ticket_id: int, magic_number: int, virtual_sl: float, virtual_tp: float, risk_recycled: bool) -> None:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO active_tickets (ticket_id, magic_number, virtual_sl, virtual_tp, risk_recycled)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(ticket_id) DO UPDATE SET
                        virtual_sl=excluded.virtual_sl,
                        virtual_tp=excluded.virtual_tp,
                        risk_recycled=excluded.risk_recycled
                ''', (ticket_id, magic_number, virtual_sl, virtual_tp, risk_recycled))
                await db.commit()
        except Exception as e:
            logger.error(f"StateLedger async update failed for ticket {ticket_id}: {e}")

    async def get_all_records(self) -> Dict[int, Dict[str, Any]]:
        records = {}
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute('SELECT * FROM active_tickets') as cursor:
                    async for row in cursor:
                        records[row['ticket_id']] = {
                            'magic_number': row['magic_number'],
                            'virtual_sl': row['virtual_sl'],
                            'virtual_tp': row['virtual_tp'],
                            'risk_recycled': bool(row['risk_recycled'])
                        }
        except Exception as e:
            logger.error(f"StateLedger get_all_records failed: {e}")
        return records

    def delete_orphan_records(self, active_tickets_in_mt5: List[int]) -> None:
        self._fire_and_forget(self._delete_orphan_records_async(active_tickets_in_mt5))

    async def _delete_orphan_records_async(self, active_tickets_in_mt5: List[int]) -> None:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if not active_tickets_in_mt5:
                    await db.execute('DELETE FROM active_tickets')
                else:
                    placeholders = ','.join('?' * len(active_tickets_in_mt5))
                    await db.execute(f'DELETE FROM active_tickets WHERE ticket_id NOT IN ({placeholders})', active_tickets_in_mt5)
                await db.commit()
        except Exception as e:
            logger.error(f"StateLedger delete_orphan_records failed: {e}")

    def delete_ticket(self, ticket_id: int) -> None:
        self._fire_and_forget(self._delete_ticket_async(ticket_id))

    async def _delete_ticket_async(self, ticket_id: int) -> None:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('DELETE FROM active_tickets WHERE ticket_id = ?', (ticket_id,))
                await db.commit()
        except Exception as e:
            logger.error(f"StateLedger delete_ticket failed for ticket {ticket_id}: {e}")
