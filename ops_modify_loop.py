import os

def modify_process_tick():
    file_path = 'src/strategy/alpha_harvester.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''                for cycle in active_cycles:
                    cycle.chop_score = chop_score'''
                    
    replace = '''                for cycle in active_cycles:
                    cycle.chop_score = chop_score
                    
                    # PHASE 2: Tick Sentinel & Risk Vault Execution
                    if cycle.state not in ["IDLE", "CLOSE_RECOVERY", "WAIT"]:
                        await self._evaluate_free_roll(cycle)
                        
                        killed = await self._evaluate_structural_kill(cycle, event.bid, ind)
                        if killed:
                            continue
                            
                        killed = await self._evaluate_time_decay(cycle, current_time)
                        if killed:
                            continue'''

    if target in content:
        content = content.replace(target, replace)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? Added Sentinel execution to process_tick loop.")
    else:
        print("?? Target not found.")

if __name__ == '__main__':
    modify_process_tick()
