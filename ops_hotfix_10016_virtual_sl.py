import os

def strip_hard_stops():
    file_path = 'src/execution/bridge.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''                    "price": round(float(price), digits),
                    "sl": round(float(sl), digits),
                    "tp": round(float(tp), digits),
                    "deviation": 30,'''
                    
    replace = '''                    "price": round(float(price), digits),
                    # VIRTUAL SL ENFORCEMENT: Stripped Hard SL/TP
                    # "sl": round(float(sl), digits),
                    # "tp": round(float(tp), digits),
                    "deviation": 30,'''

    if target in content:
        content = content.replace(target, replace)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? Successfully stripped Hard SL/TP from execution bridge.")
    else:
        print("?? Target string not found in bridge.py")

if __name__ == '__main__':
    strip_hard_stops()
