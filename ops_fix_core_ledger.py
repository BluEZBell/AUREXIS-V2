import os

def fix_campaign_ledger():
    file_path = 'src/core/campaign_ledger.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target1 = 'if event.order_type == "PROBE":'
    replace1 = 'if event.order_type in ["PROBE", "CORE"]:'
    
    target2 = 'elif event.order_type in ["SET", "SWARM", "CORE"]:'
    replace2 = 'elif event.order_type in ["SET", "SWARM"]:'

    if target1 in content and target2 in content:
        content = content.replace(target1, replace1)
        content = content.replace(target2, replace2)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? campaign_ledger.py CORE type fixed successfully.")
    else:
        print("? Target block not found")

if __name__ == '__main__':
    fix_campaign_ledger()
