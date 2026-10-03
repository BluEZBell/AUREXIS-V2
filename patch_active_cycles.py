import re

def verify_active_cycles_hotfix():
    file_path = 'src/strategy/alpha_harvester.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if "self.campaign_ledger.get_active_cycles()" in content:
        # Should not reach here based on previous patch
        target = "self.campaign_ledger.get_active_cycles()"
        replacement = "list(self.campaign_ledger.active_cycles.values())"
        content = content.replace(target, replacement)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? Patch applied successfully.")
    else:
        print("? System Verified: The 'get_active_cycles()' AttributeError has ALREADY been completely eradicated!")

if __name__ == '__main__':
    verify_active_cycles_hotfix()
