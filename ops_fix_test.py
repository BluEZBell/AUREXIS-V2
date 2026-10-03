import os

def fix_test():
    file_path = 'tests/test_alpha_harvester.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = "'adx': 15, 'adx_m15': 15.0, 'atr_m15': 10.0, 'm5_range_10': 5.0"
    replace = "'adx': 15, 'adx_m15': 15.0, 'atr_m15': 10.0, 'm5_range_10': 5.0, 'curr_price': 1905.0, 'bb_lower': 1890.0, 'bb_upper': 1930.0"
    
    if target in content:
        content = content.replace(target, replace)
        print("? Fixed test_alpha_harvester.py")
    else:
        print("?? Test target not found.")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    fix_test()
