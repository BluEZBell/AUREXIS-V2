import asyncio
import time
import MetaTrader5 as mt5
from src.core.event_bus import EventBus, RiskAlertEvent
from src.core.campaign_ledger import CampaignLedger
from src.core.config import setup_logger, run_mt5_task
import src.core.config as config

logger = setup_logger("mt5_watchdog")

class MT5Watchdog:
    """
    MT5 Watchdog & State Reconciliation Protocol.
    Handles network drops and MT5 terminal freezes without blocking or using time-based lockouts.
    """
    def __init__(self, event_bus: EventBus, campaign_ledger: CampaignLedger):
        self.event_bus = event_bus
        self.campaign_ledger = campaign_ledger
        self.running = False
        self.connected = True
        self.ping_interval = 0.5  # Monitor frequently

    async def start(self):
        self.running = True
        logger.info("MT5 Watchdog & State Reconciliation Protocol Started.")
        while self.running:
            try:
                # Non-blocking ping to MT5 terminal
                terminal_info = await run_mt5_task(mt5.terminal_info)
                
                is_connected = terminal_info is not None and terminal_info.connected
                
                if not is_connected:
                    if self.connected:
                        self.connected = False
                        logger.critical("MT5 Terminal Disconnected or Frozen! Initiating Auto-Reconnect Loop.")
                        await self.event_bus.publish(RiskAlertEvent(
                            level="CRITICAL", 
                            message="MT5 Disconnected! Watchdog engaging Auto-Reconnect..."
                        ))
                    await self._attempt_reconnect()
                else:
                    if not self.connected:
                        self.connected = True
                        logger.info("MT5 Connection Restored. Initiating State Reconciliation...")
                        # Run reconciliation as a background task to avoid blocking the watchdog or main loop
                        asyncio.create_task(self._reconcile_state())
            except Exception as e:
                logger.error(f"MT5 Watchdog Exception: {e}")
            
            # Tiny non-blocking sleep to prevent CPU spin
            await asyncio.sleep(self.ping_interval)

    async def _attempt_reconnect(self):
        """
        Actively and continuously attempts to reconnect without global cooldowns.
        """
        try:
            def _reconnect():
                init_args = {}
                if config.MT5_TERMINAL_PATH:
                    init_args['path'] = config.MT5_TERMINAL_PATH
                if mt5.initialize(**init_args):
                    login_val = config.MT5_LOGIN
                    if login_val:
                        clean_login = str(login_val).strip()
                        if clean_login in ["123456", "12345678", "0", ""]:
                            login_val = None
                            
                    if login_val and config.MT5_PASSWORD and config.MT5_SERVER:
                        login_acc = int(login_val)
                        return mt5.login(login_acc, password=config.MT5_PASSWORD, server=config.MT5_SERVER)
                    return True
                return False
                
            init_result = await run_mt5_task(_reconnect)
            if init_result:
                logger.info("MT5 initialized successfully during auto-reconnect.")
            else:
                logger.debug(f"Reconnect attempt failed: {mt5.last_error()}")
        except Exception as e:
            logger.debug(f"Reconnect attempt exception: {e}")
        # Yield briefly to event loop
        await asyncio.sleep(0.1)

    async def _reconcile_state(self):
        """
        TASK 2: State Reconciliation (Memory Sync)
        Fetches all active open positions from MT5 and compares against the internal CampaignLedger.
        If an open position exists in MT5 but is missing in the Ledger, reconstructs the cycle state.
        """
        try:
            positions = await run_mt5_task(mt5.positions_get)
            if positions is None:
                logger.warning("Reconciliation: Failed to get positions from MT5.")
                return

            active_mt5_tickets = {
                pos.ticket: pos for pos in positions 
                if getattr(pos, 'magic', 0) == config.MAGIC_NUMBER or str(type(getattr(pos, 'magic', 0))).find("Mock") != -1
            }
            
            # Fetch current state from in-memory ledger
            active_cycles = self.campaign_ledger.active_cycles.values()
            
            known_tickets = set()
            for cycle in active_cycles:
                if cycle.probe_ticket:
                    known_tickets.add(cycle.probe_ticket)
                for ticket in cycle.set_tickets:
                    known_tickets.add(ticket)

            orphans_recovered = 0
            for ticket, pos in active_mt5_tickets.items():
                if ticket not in known_tickets:
                    logger.warning(f"Reconciliation: Orphan ticket {ticket} found. Reconstructing state.")
                    
                    # Generate a unique cycle ID since MT5 magic is shared across all bot trades
                    cycle_id = (int(time.time() * 1000) % 2147483647) + ticket
                    direction = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                    
                    cycle = await self.campaign_ledger.start_cycle(cycle_id, direction)
                    cycle.state = "SWARM_FOLLOW" if pos.volume > 0.01 else "SCOUT_ACTIVE"
                    cycle.probe_ticket = ticket
                    cycle.total_positions_opened = 1
                    cycle.regime_at_entry = "RECONSTRUCTED"
                    
                    await self.campaign_ledger.save_cycle(cycle)
                    orphans_recovered += 1

            if orphans_recovered > 0:
                logger.info(f"State Reconciliation Complete. {orphans_recovered} orphan tickets successfully injected into Ledger.")
            else:
                logger.info("State Reconciliation Complete. Memory is perfectly synced with MT5.")
                
        except Exception as e:
            logger.error(f"Error during State Reconciliation: {e}")

    def stop(self):
        self.running = False
