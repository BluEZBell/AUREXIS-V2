import os

def update_app_serialization():
    file_path = 'src/web/app.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''        elif event_type == "StrategyStateEvent":
            _latest_strategy_state = dataclasses.asdict(event)
            return'''
            
    replace = '''        elif event_type == "StrategyStateEvent":
            _latest_strategy_state = dataclasses.asdict(event)
            _latest_strategy_state["adx_m15"] = getattr(event, "adx_m15", 0.0)
            _latest_strategy_state["z_score"] = getattr(event, "z_score", 0.0)
            _latest_strategy_state["atr_m15"] = getattr(event, "atr_m15", 0.0)
            return'''

    if target in content:
        content = content.replace(target, replace)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? Serialization mapping explicitly injected in app.py")
    else:
        print("?? Target string not found in app.py")

if __name__ == '__main__':
    update_app_serialization()
