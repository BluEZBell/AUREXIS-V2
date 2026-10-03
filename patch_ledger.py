import re

with open('src/core/campaign_ledger.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_method = '''        if untracked_tickets:
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
                logger.error(f"Error in realtime reconciliation loop: {e}")'''

content = re.sub(r'        if untracked_tickets:[\s\S]*?logger\.info\("State Reconciliation Complete\."\)', new_method, content)

with open('src/core/campaign_ledger.py', 'w', encoding='utf-8') as f:
    f.write(content)
