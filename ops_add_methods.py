import os

def build_sentinel_methods():
    file_path = 'src/strategy/alpha_harvester.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    methods_code = '''
    # --- PHASE 2: TICK SENTINEL & RISK VAULT ---

    async def _evaluate_time_decay(self, cycle, current_time: float) -> bool:
        """Execute close if cycle is stagnant beyond MAX_STAGNATION_SECONDS."""
        if cycle.state != "SCOUT_ACTIVE":
            return False
            
        max_stag = getattr(config, 'MAX_STAGNATION_SECONDS', 1800.0)
        duration = current_time - getattr(cycle, 'timestamp_open', current_time)
        target_mfe = getattr(config, 'STAGNATION_MFE_TARGET', 10.0)
        
        if duration > max_stag and cycle.mfe < target_mfe:
            logger.warning(f"Tick Sentinel: Cycle {cycle.cycle_id} stagnant ({duration:.0f}s). Executing Time-Decay Kill.")
            
            if cycle.probe_ticket:
                await self.event_bus.publish(OrderEvent(
                    cycle.probe_ticket, config.TRADING_SYMBOL, "CLOSE", 0.0, 0.0, "REQUEST", cycle_id=cycle.cycle_id
                ))
            for tkt in cycle.set_tickets:
                await self.event_bus.publish(OrderEvent(
                    tkt, config.TRADING_SYMBOL, "CLOSE", 0.0, 0.0, "REQUEST", cycle_id=cycle.cycle_id
                ))
                
            cycle.exit_reason = "TIME_DECAY"
            cycle.state = "IDLE"
            await self.campaign_ledger.save_cycle(cycle)
            return True
        return False

    async def _evaluate_structural_kill(self, cycle, current_price: float, ind: dict) -> bool:
        """Execute market close if price breaches Virtual SL."""
        if not cycle.probe_ticket and not cycle.set_tickets:
            return False
            
        # Dynamically calculated Virtual SL threshold based on Equity %
        acc_info = await run_mt5_task(mt5.account_info)
        eq = acc_info.equity if acc_info else 100.0
        max_risk_pct = getattr(config, 'AGGRESSIVE_RISK_PCT', 0.15)
        virtual_sl_usd = eq * -max_risk_pct
        
        if cycle.cycle_pnl <= virtual_sl_usd:
            logger.error(f"Tick Sentinel: Cycle {cycle.cycle_id} breached Virtual SL ({virtual_sl_usd:.2f} USD). Executing Structural Kill.")
            
            tickets_to_close = cycle.set_tickets + ([cycle.probe_ticket] if cycle.probe_ticket else [])
            for tkt in tickets_to_close:
                await self.event_bus.publish(OrderEvent(
                    tkt, config.TRADING_SYMBOL, "CLOSE", 0.0, current_price, "REQUEST", cycle_id=cycle.cycle_id
                ))
                
            cycle.exit_reason = "STRUCTURAL_KILL"
            cycle.state = "IDLE"
            await self.campaign_ledger.save_cycle(cycle)
            return True
            
        return False

    async def _evaluate_free_roll(self, cycle) -> bool:
        """Monitor PnL/MFE. Once True Break-Even is cleared, set state to 'FREE_ROLL'."""
        if cycle.state not in ["SCOUT_ACTIVE", "SWARM_FOLLOW", "SWARM_REVERSE"]:
            return False
            
        target_break_even_usd = getattr(config, 'FREE_ROLL_THRESHOLD_USD', 1.0)
        
        if cycle.cycle_pnl >= target_break_even_usd:
            logger.info(f"Risk Vault: Cycle {cycle.cycle_id} cleared True Break-Even (${cycle.cycle_pnl:.2f}). Upgrading to FREE_ROLL.")
            cycle.state = "FREE_ROLL"
            await self.campaign_ledger.save_cycle(cycle)
            return True
        return False
        
    # --- END PHASE 2 ---
    '''

    target_method = '''    async def check_whipsaw_lock(self, ind):'''
    
    if target_method in content and '# --- PHASE 2: TICK SENTINEL & RISK VAULT ---' not in content:
        content = content.replace(target_method, methods_code + '\n' + target_method)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? Added Sentinel & Risk Vault methods to alpha_harvester.py")
    else:
        print("?? Target string not found or methods already added.")

if __name__ == '__main__':
    build_sentinel_methods()
