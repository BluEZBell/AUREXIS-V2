import asyncio
import aiosqlite
import json
import time
import MetaTrader5 as mt5
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from src.core.event_bus import OrderEvent, PositionsUpdateEvent, CommandEvent
from src.core.config import setup_logger, run_mt5_task
import src.core.config as config

logger = setup_logger("campaign_ledger")

@dataclass
class CampaignCycle:
    cycle_id: int
    direction: str
    state: str = "IDLE" # IDLE, SCOUT_ACTIVE, SWARM_FOLLOW, SWARM_REVERSE, WHIPSAW_LOCK, WAIT
    probe_ticket: Optional[int] = None
    set_tickets: List[int] = field(default_factory=list)
    cycle_pnl: float = 0.0
    realized_pnl: float = 0.0
    dispatched_events: set = field(default_factory=set)
    
    # PHASE 19: MFE Vault & Chop State Machine
    mfe: float = 0.0
    chop_score: int = 0
    recovery_start_time: float = 0.0
    
    # PHASE 16: Journaling Metadata (in-memory only)
    timestamp_open: float = field(default_factory=time.time)
    regime_at_entry: str = "UNKNOWN"
    max_conviction_score: float = 0.0
    total_positions_opened: int = 0
    exit_reason: str = "UNKNOWN"
    is_journaled: bool = False

class CampaignLedger:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.active_cycles: Dict[int, CampaignCycle] = {}
        self._dirty_cycles = set()
        self._deleted_cycles = set()
        self._running = False
        self._flush_task = None
        self.db_path = "db/aurexis_ledger.db"
        self.event_bus.subscribe(OrderEvent, self.handle_order)
        self.event_bus.subscribe(PositionsUpdateEvent, self.handle_positions_update)
        self.event_bus.subscribe(CommandEvent, self.handle_command)

    async def handle_command(self, event: CommandEvent):
        if event.action == "PANIC_HALT":
            for cycle in self.active_cycles.values():
                cycle.exit_reason = "PANIC_HALT"

    async def journal_cycle(self, cycle: CampaignCycle):
        import asyncio
        import os
        from datetime import datetime
        
        def write_csv():
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            csv_path = os.path.join(log_dir, "institutional_journal.csv")
            file_exists = os.path.exists(csv_path)
            
            with open(csv_path, mode='a', encoding='utf-8') as f:
                if not file_exists:
                    f.write("Timestamp_Open,Timestamp_Close,Cycle_ID,Direction,Total_Positions_Opened,Regime_At_Entry,Max_Conviction_Score,Total_Realized_PnL,Exit_Reason\n")
                
                dt_open = datetime.fromtimestamp(cycle.timestamp_open).strftime('%Y-%m-%d %H:%M:%S')
                dt_close = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                line = f"{dt_open},{dt_close},{cycle.cycle_id},{cycle.direction},{cycle.total_positions_opened},{cycle.regime_at_entry},{cycle.max_conviction_score:.2f},{cycle.realized_pnl:.2f},{cycle.exit_reason}\n"
                f.write(line)
                
        await asyncio.to_thread(write_csv)
        logger.info(f"CampaignLedger: Cycle {cycle.cycle_id} asynchronously journaled to CSV.")

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

    async def _batch_flush(self):
        logger.info("CampaignLedger: Async Batch Flushing background task started.")
        while self._running:
            await asyncio.sleep(1.0)
            
            if not self._dirty_cycles and not self._deleted_cycles:
                continue
                
            dirty_to_process = list(self._dirty_cycles)
            deleted_to_process = list(self._deleted_cycles)
            
            self._dirty_cycles.clear()
            self._deleted_cycles.clear()
            
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    for cycle_id in deleted_to_process:
                        await db.execute("DELETE FROM cycles WHERE cycle_id=?", (cycle_id,))
                        await db.execute("DELETE FROM cycle_sets WHERE cycle_id=?", (cycle_id,))
                        await db.execute("DELETE FROM dispatched_events WHERE cycle_id=?", (cycle_id,))
                        
                    for cycle_id in dirty_to_process:
                        cycle = self.active_cycles.get(cycle_id)
                        if cycle:
                            await db.execute("""
                                INSERT INTO cycles (cycle_id, direction, state, probe_ticket, cycle_pnl, realized_pnl, updated_at, mfe, chop_score, recovery_start_time)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(cycle_id) DO UPDATE SET
                                    state=excluded.state,
                                    probe_ticket=excluded.probe_ticket,
                                    cycle_pnl=excluded.cycle_pnl,
                                    realized_pnl=excluded.realized_pnl,
                                    updated_at=excluded.updated_at,
                                    mfe=excluded.mfe,
                                    chop_score=excluded.chop_score,
                                    recovery_start_time=excluded.recovery_start_time
                            """, (
                                cycle.cycle_id, cycle.direction, cycle.state,
                                cycle.probe_ticket, cycle.cycle_pnl, cycle.realized_pnl, time.time(),
                                cycle.mfe, cycle.chop_score, cycle.recovery_start_time
                            ))
                            
                            for ticket in cycle.set_tickets:
                                await db.execute("""
                                    INSERT OR IGNORE INTO cycle_sets (cycle_id, ticket) VALUES (?, ?)
                                """, (cycle.cycle_id, ticket))
                                
                            for event_name in cycle.dispatched_events:
                                await db.execute("""
                                    INSERT OR IGNORE INTO dispatched_events (cycle_id, event_name) VALUES (?, ?)
                                """, (cycle.cycle_id, event_name))
                                
                    await db.commit()
            except Exception as e:
                logger.error(f"CampaignLedger: Batch Flush Error: {e}")
                # Re-add to sets on failure so we can try again next tick
                self._dirty_cycles.update(dirty_to_process)
                self._deleted_cycles.update(deleted_to_process)

    async def initialize(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cycles (
                    cycle_id INTEGER PRIMARY KEY,
                    direction TEXT,
                    state TEXT,
                    probe_ticket INTEGER,
                    cycle_pnl REAL,
                    realized_pnl REAL,
                    updated_at REAL,
                    mfe REAL DEFAULT 0.0,
                    chop_score INTEGER DEFAULT 0,
                    recovery_start_time REAL DEFAULT 0.0
                )
            """)
            # Phase 19: Safe alter table for existing DBs
            try: await db.execute("ALTER TABLE cycles ADD COLUMN mfe REAL DEFAULT 0.0")
            except Exception: pass
            try: await db.execute("ALTER TABLE cycles ADD COLUMN chop_score INTEGER DEFAULT 0")
            except Exception: pass
            try: await db.execute("ALTER TABLE cycles ADD COLUMN recovery_start_time REAL DEFAULT 0.0")
            except Exception: pass
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cycle_sets (
                    cycle_id INTEGER,
                    ticket INTEGER,
                    PRIMARY KEY (cycle_id, ticket)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS dispatched_events (
                    cycle_id INTEGER,
                    event_name TEXT,
                    PRIMARY KEY (cycle_id, event_name)
                )
            """)
            await db.commit()
        logger.info("Anti-Amnesia SQLite Ledger Initialized (WAL Mode)")
        
        self._running = True
        self._flush_task = asyncio.create_task(self._batch_flush())

    def stop(self):
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()

    async def save_cycle(self, cycle: CampaignCycle):
        if cycle.state == "IDLE" and not cycle.is_journaled:
            await self.journal_cycle(cycle)
            cycle.is_journaled = True
            
        self.active_cycles[cycle.cycle_id] = cycle
        self._dirty_cycles.add(cycle.cycle_id)

    async def load_from_db(self):
        logger.info("Loading active cycles from Ledger DB...")
        # 1. Load active cycles from DB
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM cycles")
            rows = await cursor.fetchall()
            for row in rows:
                c = CampaignCycle(
                    cycle_id=row["cycle_id"],
                    direction=row["direction"],
                    state=row["state"],
                    probe_ticket=row["probe_ticket"],
                    cycle_pnl=row["cycle_pnl"],
                    realized_pnl=row["realized_pnl"],
                    mfe=row["mfe"] if "mfe" in row.keys() else 0.0,
                    chop_score=row["chop_score"] if "chop_score" in row.keys() else 0,
                    recovery_start_time=row["recovery_start_time"] if "recovery_start_time" in row.keys() else 0.0
                )
                
                # Load sets
                s_cursor = await db.execute("SELECT ticket FROM cycle_sets WHERE cycle_id=?", (c.cycle_id,))
                s_rows = await s_cursor.fetchall()
                c.set_tickets = [r["ticket"] for r in s_rows]
                
                # Load events
                e_cursor = await db.execute("SELECT event_name FROM dispatched_events WHERE cycle_id=?", (c.cycle_id,))
                e_rows = await e_cursor.fetchall()
                c.dispatched_events = set([r["event_name"] for r in e_rows])
                
                self.active_cycles[c.cycle_id] = c
                
        logger.info(f"Ledger DB load complete. {len(self.active_cycles)} cycles active.")

    async def load_and_reconcile(self) -> None:
        logger.info("Starting State Reconciliation...")
        await self.load_from_db()
        
        initialized = await run_mt5_task(mt5.initialize)
        if not initialized:
            logger.error("Reconciliation failed: Could not initialize MT5.")
            return

        positions = await run_mt5_task(mt5.positions_get)
        if positions is None:
            logger.error("Reconciliation failed: Could not retrieve positions from MT5.")
            return

        open_tickets = {pos.ticket for pos in positions}
        db_tickets = set()
        
        for cycle_id, cycle in list(self.active_cycles.items()):
            active_in_cycle = False
            
            if cycle.probe_ticket is not None:
                if cycle.probe_ticket in open_tickets:
                    active_in_cycle = True
                    db_tickets.add(cycle.probe_ticket)
                else:
                    logger.warning(f"Reconciliation: Probe ticket {cycle.probe_ticket} not found in MT5. Removing.")
                    cycle.probe_ticket = None
            
            valid_set_tickets = []
            for ticket in cycle.set_tickets:
                if ticket in open_tickets:
                    active_in_cycle = True
                    valid_set_tickets.append(ticket)
                    db_tickets.add(ticket)
                else:
                    logger.warning(f"Reconciliation: Set ticket {ticket} not found in MT5. Removing.")
            
            cycle.set_tickets = valid_set_tickets
            
            if not active_in_cycle:
                logger.info(f"Reconciliation: Cycle {cycle_id} has no active tickets. Closing cycle.")
                await self.close_cycle(cycle_id)
            else:
                await self.save_cycle(cycle)
        
        untracked_tickets = open_tickets - db_tickets
        if untracked_tickets:
            logger.warning(f"Reconciliation: Found untracked MT5 tickets: {untracked_tickets}")
            for pos in positions:
                if pos.ticket in untracked_tickets and getattr(pos, 'magic', None) == config.MAGIC_NUMBER:
                    logger.info(f"Reconciliation: Adopting orphan ticket {pos.ticket}.")
                    
                    pos_type = getattr(pos, 'type', mt5.POSITION_TYPE_BUY)
                    direction = "BUY" if pos_type == mt5.POSITION_TYPE_BUY else "SELL"
                    new_cycle_id = int(time.time() * 1000) + pos.ticket
                    
                    cycle = CampaignCycle(cycle_id=new_cycle_id, direction=direction, state="SCOUT_ACTIVE")
                    cycle.probe_ticket = pos.ticket
                    cycle.total_positions_opened = 1
                    
                    self.active_cycles[new_cycle_id] = cycle
                    await self.save_cycle(cycle)

        logger.info("State Reconciliation Complete.")

    def start_realtime_reconciliation(self):
        import asyncio
        asyncio.create_task(self._realtime_reconciliation_loop())

    async def _realtime_reconciliation_loop(self):
        import asyncio
        import time
        while True:
            await asyncio.sleep(15)
            try:
                positions = await run_mt5_task(mt5.positions_get)
                if positions is None:
                    continue
                
                open_tickets = {pos.ticket for pos in positions if getattr(pos, 'magic', None) == config.MAGIC_NUMBER}
                db_tickets = set()
                
                for cycle in list(self.active_cycles.values()):
                    if cycle.probe_ticket: db_tickets.add(cycle.probe_ticket)
                    for t in cycle.set_tickets: db_tickets.add(t)
                
                untracked_tickets = open_tickets - db_tickets
                if untracked_tickets:
                    logger.warning(f"REAL-TIME RECONCILIATION: Ghost positions detected due to latency/drop: {untracked_tickets}. Adopting...")
                    for pos in positions:
                        if pos.ticket in untracked_tickets:
                            pos_type = getattr(pos, 'type', 0)
                            direction = "BUY" if pos_type == 0 else "SELL"
                            new_cycle_id = int(time.time() * 1000) + pos.ticket
                            
                            cycle = CampaignCycle(cycle_id=new_cycle_id, direction=direction, state="SCOUT_ACTIVE")
                            cycle.probe_ticket = pos.ticket
                            cycle.total_positions_opened = 1
                            
                            self.active_cycles[new_cycle_id] = cycle
                            await self.save_cycle(cycle)
                            logger.info(f"Adopted Ghost Ticket {pos.ticket} into new Cycle {new_cycle_id}.")
            except Exception as e:
                logger.error(f"Error in realtime reconciliation loop: {e}")

    def get_cycle(self, cycle_id: int) -> Optional[CampaignCycle]:
        return self.active_cycles.get(cycle_id)

    def _mark_deleted(self, cycle_id: int):
        self.active_cycles.pop(cycle_id, None)
        self._dirty_cycles.discard(cycle_id)
        self._deleted_cycles.add(cycle_id)

    async def start_cycle(self, cycle_id: int, direction: str) -> CampaignCycle:
        if cycle_id not in self.active_cycles:
            cycle = CampaignCycle(cycle_id=cycle_id, direction=direction, state="SCOUT_ACTIVE")
            self.active_cycles[cycle_id] = cycle
            logger.info(f"Started new Campaign Cycle: {cycle_id} ({direction})")
            await self.save_cycle(cycle)
        return self.active_cycles[cycle_id]

    async def handle_order(self, event: OrderEvent):
        if event.status == "FILLED" and event.cycle_id != 0:
            cycle = self.get_cycle(event.cycle_id)
            if not cycle:
                cycle = await self.start_cycle(event.cycle_id, event.direction)
            
            should_save = False
            if event.order_type in ["PROBE", "CORE"]:
                cycle.probe_ticket = event.ticket
                cycle.total_positions_opened += 1
                cycle.regime_at_entry = getattr(event, "regime", "UNKNOWN")
                cycle.max_conviction_score = max(float(cycle.max_conviction_score), float(getattr(event, "conviction", 0.0)))
                logger.info(f"Cycle {event.cycle_id}: Logged PROBE ticket {event.ticket} with Conviction: {cycle.max_conviction_score}")
                should_save = True
            elif event.order_type in ["SET", "SWARM"]:
                if event.ticket not in cycle.set_tickets:
                    cycle.set_tickets.append(event.ticket)
                    cycle.total_positions_opened += 1
                    cycle.max_conviction_score = max(float(cycle.max_conviction_score), float(getattr(event, "conviction", 0.0)))
                    logger.info(f"Cycle {event.cycle_id}: Logged SET ticket {event.ticket} with Conviction: {cycle.max_conviction_score}")
                    should_save = True
                    
            if should_save:
                await self.save_cycle(cycle)
                
        elif event.status == "CLOSED_SYNC":
            ticket = event.ticket
            net_pnl = event.price
            for cycle_id, cycle in list(self.active_cycles.items()):
                if ticket == cycle.probe_ticket or ticket in cycle.set_tickets:
                    cycle.realized_pnl += net_pnl
                    logger.info(f"Cycle {cycle_id}: Ticket {ticket} closed. Realized PnL added: {net_pnl:.2f}. Total Realized: {cycle.realized_pnl:.2f}")
                    if ticket == cycle.probe_ticket:
                        cycle.probe_ticket = None
                    elif ticket in cycle.set_tickets:
                        cycle.set_tickets.remove(ticket)
                    
                    await self.save_cycle(cycle)
                    
                    # If empty, we can clean up
                    if cycle.probe_ticket is None and len(cycle.set_tickets) == 0:
                        if cycle.state != "IDLE":
                            cycle.state = "IDLE"
                            if cycle.exit_reason == "UNKNOWN":
                                if cycle.realized_pnl > 0:
                                    cycle.exit_reason = "BROKER_TP"
                                else:
                                    cycle.exit_reason = "HARD_SL_SPIKE"
                            await self.save_cycle(cycle)
                            
                        logger.info(f"Cycle {cycle_id} has no tickets after CLOSED_SYNC. Purging from in-memory cache and marking deleted.")
                        self._mark_deleted(cycle_id)
                    break
        elif event.status in ["REJECTED", "FAILED", "CANCELLED"]:
            if event.cycle_id in self.active_cycles:
                self._mark_deleted(event.cycle_id)
                logger.warning(f"Cycle {event.cycle_id} purged from Ledger due to REJECTED/FAILED order.")

    async def handle_positions_update(self, event: PositionsUpdateEvent):
        for cycle_id, cycle in list(self.active_cycles.items()):
            floating_pnl = 0.0
            has_active_tickets = False
            for pos in event.positions:
                ticket = pos["ticket"]
                if ticket == cycle.probe_ticket or ticket in cycle.set_tickets:
                    floating_pnl += pos["profit"]
                    has_active_tickets = True
            
            # Total cycle PnL = floating + realized
            new_pnl = floating_pnl + cycle.realized_pnl
            
            if abs(new_pnl - cycle.cycle_pnl) > 0.01:
                cycle.cycle_pnl = new_pnl
                await self.save_cycle(cycle)
            
            if not has_active_tickets and (cycle.probe_ticket is None and len(cycle.set_tickets) == 0):
                # Cleaned up already in CLOSED_SYNC normally, but just in case
                if cycle_id in self.active_cycles:
                    if cycle.state != "IDLE":
                        cycle.state = "IDLE"
                        if cycle.exit_reason == "UNKNOWN":
                            if cycle.realized_pnl > 0:
                                cycle.exit_reason = "BROKER_TP"
                            else:
                                cycle.exit_reason = "HARD_SL_SPIKE"
                        await self.save_cycle(cycle)
                        
                    self._mark_deleted(cycle_id)

    async def get_active_cycles(self) -> list:
        # Phase 20: Return from fast In-Memory state cache to avoid sqlite locks
        return list(self.active_cycles.values())

    async def close_cycle(self, cycle_id: int):
        if cycle_id in self.active_cycles:
            logger.info(f"Closing Campaign Cycle: {cycle_id}")
            cycle = self.active_cycles.get(cycle_id)
            if not cycle:
                return
            if cycle.state != "IDLE":
                cycle.state = "IDLE"
                if cycle.exit_reason == "UNKNOWN":
                    if cycle.realized_pnl > 0:
                        cycle.exit_reason = "BROKER_TP"
                    else:
                        cycle.exit_reason = "HARD_SL_SPIKE"
                await self.save_cycle(cycle)
                
            self._mark_deleted(cycle_id)



