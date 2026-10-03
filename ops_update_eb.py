import os

def update_event_bus():
    file_path = 'src/core/event_bus.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''class StrategyStateEvent:
    strategy_id: str
    cycle_state: str
    swarm_type: str
    scout_dir: str
    whipsaw_locked: bool
    whipsaw_locked_until: float
    current_score: float'''
    
    replace = '''class StrategyStateEvent:
    strategy_id: str
    cycle_state: str
    swarm_type: str
    scout_dir: str
    whipsaw_locked: bool
    whipsaw_locked_until: float
    current_score: float
    adx_m15: float = 0.0
    z_score: float = 0.0
    atr_m15: float = 0.0'''

    if target in content:
        content = content.replace(target, replace)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? EventBus updated.")
    else:
        print("?? Target not found in EventBus.")

if __name__ == '__main__':
    update_event_bus()
