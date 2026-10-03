with open('src/execution/sentinel.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''            current_mfe = self.mfe_vault.get(ticket, 0.0)
            new_mfe = max(current_mfe, current_profit)
            self.mfe_vault[ticket] = new_mfe
            
            floor = None
            if new_mfe >= 15.0:
                floor = new_mfe * 0.5
            elif new_mfe >= 10.0:
                floor = 2.0
            elif new_mfe >= 4.0:
                floor = 0.20'''

new_block = '''            current_mfe = self.mfe_vault.get(ticket, 0.0)
            new_mfe = max(current_mfe, current_profit)
            self.mfe_vault[ticket] = new_mfe
            
            sym_info = await run_mt5_task(lambda: mt5.symbol_info(config.TRADING_SYMBOL))
            tick = await run_mt5_task(lambda: mt5.symbol_info_tick(config.TRADING_SYMBOL))
            if not sym_info or not tick:
                continue
                
            spread_in_ticks = (tick.ask - tick.bid) / sym_info.trade_tick_size
            spread_cost_usd = spread_in_ticks * sym_info.trade_tick_value * pos.volume
            spread_cost_usd = max(spread_cost_usd, 0.50 * (pos.volume / 0.10))
            
            floor = None
            activation_tier_2 = spread_cost_usd * 10.0
            activation_tier_1 = spread_cost_usd * 3.0
            
            if new_mfe >= activation_tier_2:
                floor = new_mfe * 0.5
            elif new_mfe >= activation_tier_1:
                floor = spread_cost_usd * 1.5'''

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('src/execution/sentinel.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patch applied successfully.")
else:
    print("Could not find the block to replace.")
