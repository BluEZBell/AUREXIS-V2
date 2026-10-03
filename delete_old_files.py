import os

def delete_if_exists(path):
    if os.path.exists(path):
        os.remove(path)
        print(f"Deleted {path}")
    else:
        print(f"File {path} not found")

delete_if_exists('src/alpha/alpha_scorer.py')
delete_if_exists('src/alpha/regime_radar.py')
