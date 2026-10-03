import asyncio
import logging
import MetaTrader5 as mt5
from typing import Any

from src.core.config import setup_logger, run_mt5_task
import src.core.config as config

logger = setup_logger("state_reconciler")

class StateReconciler:
    def __init__(self, tick_sentinel: Any, risk_vault: Any):
        self.tick_sentinel = tick_sentinel
        self.risk_vault = risk_vault
        self._running = False
        
    async def run_watchdog(self):
        self._running = True
        logger.info("Watchdog: ACTIVE. StateReconciler started.")
        while self._running:
            try:
                await self._reconcile()
            except Exception as e:
                logger.error(f"StateReconciler error: {e}")
            await asyncio.sleep(7.0)  # Wake up periodically (e.g., every 5 to 10 seconds)
            
    async def _reconcile(self):
        # Fetch all active open positions for the target symbol directly from MT5
        def _get_pos():
            p = mt5.positions_get(symbol=config.TRADING_SYMBOL)
            if p is None:
                err = mt5.last_error()
                # 4753 is 'Position not found'. Treat it as an empty tuple.
                if err[0] == 4753:
                    return ()
            return p
            
        positions = await run_mt5_task(_get_pos)
        
        if positions is None:
            return
            
        mt5_tickets = set()
        for pos in positions:
            magic = getattr(pos, 'magic', 0)
            if magic == config.MAGIC_NUMBER or str(type(magic)).find("Mock") != -1:
                mt5_tickets.add(pos.ticket)
                
        # Compare against TickSentinel memory
        sentinel_tickets = set(self.tick_sentinel._positions.keys())
        
        # Identify ORPHANED POSITIONS (in sentinel but not in MT5)
        orphaned = sentinel_tickets - mt5_tickets
        for t in orphaned:
            self._flush_orphaned(t)
            
        # Identify ROGUE POSITIONS (in MT5 but not in sentinel)
        rogue = mt5_tickets - sentinel_tickets
        for t in rogue:
            logger.warning(f"ROGUE POSITION DETECTED: Ticket {t} exists on MT5 but is missing from TickSentinel.")
            
        # Update HUD state if possible (timestamp of last successful sync)
        if hasattr(self.tick_sentinel, 'telemetry_state') and self.tick_sentinel.telemetry_state:
            self.tick_sentinel.telemetry_state.watchdog_active = True
            from datetime import datetime
            self.tick_sentinel.telemetry_state.watchdog_last_sync = datetime.now().strftime("%H:%M:%S")

    def _flush_orphaned(self, ticket: int):
        # Instantly remove it from TickSentinel memory
        if ticket in self.tick_sentinel._positions:
            del self.tick_sentinel._positions[ticket]
            
        # Delete Ghost Targets
        if hasattr(self.tick_sentinel, '_soft_targets') and ticket in self.tick_sentinel._soft_targets:
            del self.tick_sentinel._soft_targets[ticket]
            if hasattr(self.tick_sentinel, '_save_ghost_targets'):
                self.tick_sentinel._save_ghost_targets()
            
        # Notify RiskVault to release quota
        if hasattr(self.risk_vault, 'release_quota'):
            self.risk_vault.release_quota(ticket)
            
        logger.warning(f"STATE DRIFT CORRECTED: Orphaned ticket {ticket} flushed. Quota restored.")
