import os

def hotfix_telemetry():
    file_path = 'src/strategy/alpha_harvester.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '                global_state = "TREND_ACTIVE" if chop_score < 3 else "RANGE_ACTIVE"'
    
    replace = '''                adx_val = ind.get('adx_m15', 20.0)
                global_state = "TREND_ACTIVE" if adx_val >= 22.0 else "RANGE_ACTIVE (MEAN-REV)"'''

    if target in content:
        content = content.replace(target, replace)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? Patch applied successfully: Synchronized global_state telemetry.")
    else:
        print("?? Patch skipped: Target string not found.")

if __name__ == '__main__':
    hotfix_telemetry()
