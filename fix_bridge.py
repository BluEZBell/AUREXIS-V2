import re

with open('src/execution/bridge.py', 'r', encoding='utf-8') as f:
    content = f.read()

verify_code = r'''    async def _verify_execution_direction(self, signal: SignalEvent) -> bool:
        def _check():
            rates = mt5.copy_rates_from_pos(config.TRADING_SYMBOL, mt5.TIMEFRAME_M5, 0, 20)
            if rates is None or len(rates) < 20:
                return True
                
            closes = np.array([r['close'] for r in rates])
            sma = np.mean(closes)
            std = np.std(closes, ddof=0)
            bb_upper = sma + (2.0 * std)
            bb_lower = sma - (2.0 * std)
            
            tick = mt5.symbol_info_tick(config.TRADING_SYMBOL)
            if not tick:
                return True
                
            current_price = tick.ask if signal.direction == "BUY" else tick.bid
            
            if signal.direction == "BUY" and current_price >= bb_upper - (bb_upper - bb_lower) * 0.15:
                return False
            if signal.direction == "SELL" and current_price <= bb_lower + (bb_upper - bb_lower) * 0.15:
                return False
            return True
            
        result = await run_mt5_task(_check)
        if result is False:
            if signal.direction == "BUY":
                logger.warning("DIRECTIONAL SHIELD: Rejected BUY signal at the Upper Band.")
                # We can't await self._log_and_publish in sync func, but we are in async here
            else:
                logger.warning("DIRECTIONAL SHIELD: Rejected SELL signal at the Lower Band.")
            return False
        return True
'''

process_old = r'''    async def process_signal\(self, signal: SignalEvent\):
        if signal.direction not in \["BUY", "SELL"\]:
            return
            
        is_swarm = getattr\(signal, "strategy_id", ""\) in \["SWARM_TREND", "SWARM_REVERSAL"\]
            
        if not is_swarm and \(time.time\(\) - self._last_order_time < 3.0\):
            await self._log_and_publish\("DOOMSDAY SHIELD 1 \(Machine-Gun Lock\) triggered. Dropping signal."\)
            return
            
        async with self._order_lock:
            if not is_swarm and \(time.time\(\) - self._last_order_time < 3.0\):
                return

            if not await self._check_doomsday_shields\(signal\):
                return'''

process_new = r'''    async def _verify_execution_direction(self, signal: SignalEvent) -> bool:
        def _check():
            rates = mt5.copy_rates_from_pos(config.TRADING_SYMBOL, mt5.TIMEFRAME_M5, 0, 20)
            if rates is None or len(rates) < 20:
                return True
                
            closes = np.array([r['close'] for r in rates])
            sma = np.mean(closes)
            std = np.std(closes, ddof=0)
            bb_upper = sma + (2.0 * std)
            bb_lower = sma - (2.0 * std)
            
            tick = mt5.symbol_info_tick(config.TRADING_SYMBOL)
            if not tick:
                return True
                
            current_price = tick.ask if signal.direction == "BUY" else tick.bid
            
            if signal.direction == "BUY" and current_price >= bb_upper - (bb_upper - bb_lower) * 0.15:
                return False
            if signal.direction == "SELL" and current_price <= bb_lower + (bb_upper - bb_lower) * 0.15:
                return False
            return True
            
        result = await run_mt5_task(_check)
        if result is False:
            if signal.direction == "BUY":
                await self._log_and_publish("DIRECTIONAL SHIELD: Rejected BUY signal at the Upper Band.", "warning")
            else:
                await self._log_and_publish("DIRECTIONAL SHIELD: Rejected SELL signal at the Lower Band.", "warning")
            return False
        return True

    async def process_signal(self, signal: SignalEvent):
        if signal.direction not in ["BUY", "SELL"]:
            return
            
        is_swarm = getattr(signal, "strategy_id", "") in ["SWARM_TREND", "SWARM_REVERSAL"]
            
        if not is_swarm and (time.time() - self._last_order_time < 3.0):
            await self._log_and_publish("DOOMSDAY SHIELD 1 (Machine-Gun Lock) triggered. Dropping signal.")
            return
            
        async with self._order_lock:
            if not is_swarm and (time.time() - self._last_order_time < 3.0):
                return

            # Independent Execution-Layer Directional Gatekeeper
            if not await self._verify_execution_direction(signal):
                return

            if not await self._check_doomsday_shields(signal):
                return'''

content = re.sub(process_old, process_new, content)

with open('src/execution/bridge.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Injected Execution-Layer Directional Gatekeeper.")
