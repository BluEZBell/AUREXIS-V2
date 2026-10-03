import os
import re

def patch_campaign_ledger():
    file_path = 'src/core/campaign_ledger.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = 'elif event.order_type == "SET":'
    replace = 'elif event.order_type in ["SET", "SWARM", "CORE"]:'

    if target in content:
        content = content.replace(target, replace)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? campaign_ledger.py patched successfully.")
    else:
        print("? Target block not found in campaign_ledger.py")

if __name__ == '__main__':
    patch_campaign_ledger()
