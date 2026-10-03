import os

def refactor_process_tick():
    file_path = 'src/strategy/alpha_harvester.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Inject scorer initialization
    if "self.scorer = AlphaScorer()" not in content:
        init_target = '''        from src.analytics.ml_oracle import MLOracle
        self.oracle = MLOracle()'''
        init_replace = '''        from src.analytics.ml_oracle import MLOracle
        self.oracle = MLOracle()
        
        from src.alpha.alpha_scorer import AlphaScorer
        self.scorer = AlphaScorer()'''
        content = content.replace(init_target, init_replace)

    target_scout_block = '''            if len(active_cycles) == 0 and self.auto_sniper:
                adx_m15 = ind.get('adx_m15', 20.0)
                if await self.check_whipsaw_lock(ind) and adx_m15 >= 22.0:
                    return
                    
                # SCOUT Entry Logic (Omni-Directional Radar)
                conv_buy = await self._calculate_conviction("BUY", chop_score)
                conv_sell = await self._calculate_conviction("SELL", chop_score)
                
                direction = None
                conv = 0.0
                if conv_buy >= 40.0 and conv_buy > conv_sell:
                    direction = "BUY"
                    conv = conv_buy
                elif conv_sell >= 40.0 and conv_sell > conv_buy:
                    direction = "SELL"
                    conv = conv_sell
                    
                if not direction:
                    # Do not return yet, we must update telemetry
                    pass
                else:
                    cycle_id = int(time.time())
                    logger.info(f"SCOUT ENTRY: {direction}. Initializing Cycle {cycle_id} with Conviction: {conv}")
                    acc_info = await run_mt5_task(mt5.account_info)
                    current_equity = acc_info.equity if acc_info else 100.0
                    dynamic_vol = self.risk_manager.calculate_lot_size(current_equity, atr=ind.get('atr_m15', 200.0))
                    adx_m15 = ind.get('adx_m15', 20.0)
                    order_type = "MEAN_REV" if adx_m15 < 22.0 else "PROBE"
                    sig = SignalEvent(event.symbol, direction, self.strategy_id, event.bid, conviction=conv, volume=dynamic_vol, cycle_id=cycle_id, order_type=order_type)
                    await self.event_bus.publish(sig)
                    self._cooldown_until = current_time + 60.0
                
            else:
                for cycle in active_cycles:'''

    replace_scout_block = '''            # 1. Active Cycles State Maintenance
            for cycle in active_cycles:'''

    if target_scout_block in content:
        content = content.replace(target_scout_block, replace_scout_block)
        print("? Replaced old scout logic.")
    else:
        print("?? Target scout block not found.")
        
    target_telemetry_block = '''            active_cycles = await self.campaign_ledger.get_active_cycles()
            if active_cycles:
                primary_cycle = active_cycles[0]
                global_state = primary_cycle.state'''
                
    replace_telemetry_block = '''            # 2. PHASE 3.5: Execution Gateway
            if self.auto_sniper:
                signal = await self.scorer.evaluate(ind)
                
                if signal.score < 50:
                    pass # Noise Filter
                elif 50 <= signal.score <= 74:
                    if len(active_cycles) == 0:
                        if not await self.check_whipsaw_lock(ind):
                            logger.info(f"Gateway: Initiating PROBE ({signal.direction}) at score {signal.score} [Regime: {signal.regime}]")
                            cycle_id = int(time.time())
                            acc_info = await run_mt5_task(mt5.account_info)
                            eq = acc_info.equity if acc_info else 100.0
                            vol = self.risk_manager.calculate_lot_size(eq, atr=ind.get('atr_m15', 200.0))
                            
                            sig = SignalEvent(event.symbol, signal.direction, self.strategy_id, event.bid, conviction=signal.score, volume=vol, cycle_id=cycle_id, order_type="PROBE")
                            await self.event_bus.publish(sig)
                            self._cooldown_until = current_time + 60.0
                elif signal.score >= 75:
                    if len(active_cycles) == 0:
                        if not await self.check_whipsaw_lock(ind):
                            logger.info(f"Gateway: Initiating CORE ({signal.direction}) at score {signal.score} [Regime: {signal.regime}]")
                            cycle_id = int(time.time())
                            acc_info = await run_mt5_task(mt5.account_info)
                            eq = acc_info.equity if acc_info else 100.0
                            vol = self.risk_manager.calculate_lot_size(eq, atr=ind.get('atr_m15', 200.0))
                            
                            sig = SignalEvent(event.symbol, signal.direction, self.strategy_id, event.bid, conviction=signal.score, volume=vol, cycle_id=cycle_id, order_type="CORE")
                            await self.event_bus.publish(sig)
                            self._cooldown_until = current_time + 60.0
                    else:
                        for cycle in active_cycles:
                            if getattr(cycle, 'state', '') == "FREE_ROLL" and getattr(cycle, 'direction', '') == signal.direction:
                                logger.info(f"Gateway: Initiating SWARM ({signal.direction}) Pyramiding at score {signal.score}")
                                cycle.state = "SWARM_ACTIVE"
                                await self.campaign_ledger.save_cycle(cycle)
                                
                                sig = SignalEvent(event.symbol, signal.direction, self.strategy_id, event.bid, conviction=signal.score, volume=0.0, cycle_id=cycle.cycle_id, order_type="SWARM")
                                await self.event_bus.publish(sig)
                                self._cooldown_until = current_time + 60.0

            active_cycles = await self.campaign_ledger.get_active_cycles()
            if active_cycles:
                primary_cycle = active_cycles[0]
                global_state = primary_cycle.state'''

    if target_telemetry_block in content:
        content = content.replace(target_telemetry_block, replace_telemetry_block)
        print("? Injected Gateway logic.")
    else:
        print("?? Target telemetry block not found.")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    refactor_process_tick()
