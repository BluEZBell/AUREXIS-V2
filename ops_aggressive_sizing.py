import os

def aggressive_sizing():
    file_path = 'src/execution/risk_manager.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''        # Continuous mathematical scaling function
        base_risk_pct = getattr(config, 'BASE_RISK_PCT', 0.02)
        risk_pct = base_risk_pct
        if PROFILE_MODE == 'EXAM_MODE':
            risk_pct = getattr(config, 'EXAM_RISK_PCT', 0.005)'''
            
    replace = '''        # Continuous mathematical scaling function
        base_risk_pct = getattr(config, 'BASE_RISK_PCT', 0.02)
        risk_pct = base_risk_pct
        if PROFILE_MODE == 'EXAM_MODE':
            risk_pct = getattr(config, 'EXAM_RISK_PCT', 0.005)
        elif equity < 500.0:
            risk_pct = getattr(config, 'AGGRESSIVE_RISK_PCT', 0.15)'''

    if target in content:
        content = content.replace(target, replace)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? Hotfix applied to risk_manager.py")
    else:
        print("?? Target string not found in risk_manager.py")

if __name__ == '__main__':
    aggressive_sizing()
