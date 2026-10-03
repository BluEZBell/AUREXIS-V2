import os

def update_harvester():
    file_path = 'src/strategy/alpha_harvester.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''            state_event = StrategyStateEvent(
                strategy_id=self.strategy_id,
                cycle_state=global_state,
                swarm_type=swarm_type,
                scout_dir=hypothetical_dir,
                whipsaw_locked=whipsaw_locked,
                whipsaw_locked_until=self.whipsaw_locked_until,
                current_score=self.current_score
            )'''
    
    replace = '''            # Calculate Z-Score for telemetry
            curr_price = ind.get('curr_price', 0.0)
            ema20_m15 = ind.get('ema20_m15', 0.0)
            bb_upper = ind.get('bb_upper', 0.0)
            atr_m15 = ind.get('atr_m15', 0.0)
            adx_m15 = ind.get('adx_m15', 0.0)
            std_dev = (bb_upper - ema20_m15) / 2.0 if bb_upper > ema20_m15 else atr_m15
            z_score = (curr_price - ema20_m15) / std_dev if std_dev > 0 else 0.0

            state_event = StrategyStateEvent(
                strategy_id=self.strategy_id,
                cycle_state=global_state,
                swarm_type=swarm_type,
                scout_dir=hypothetical_dir,
                whipsaw_locked=whipsaw_locked,
                whipsaw_locked_until=self.whipsaw_locked_until,
                current_score=self.current_score,
                adx_m15=adx_m15,
                z_score=z_score,
                atr_m15=atr_m15
            )'''

    if target in content:
        content = content.replace(target, replace)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? AlphaHarvester updated.")
    else:
        print("?? Target not found in AlphaHarvester.")

if __name__ == '__main__':
    update_harvester()
