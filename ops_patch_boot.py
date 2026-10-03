import os
import re

def patch_main_and_harvester():
    # 1. Patch main.py to load oracle
    with open('src/main.py', 'r', encoding='utf-8') as f:
        main_content = f.read()
    
    target_main = '''        # 4. Initialize Harvester
        logger.info("[4/5] AlphaHarvester Strategy engaged.")'''
    replace_main = '''        # 4. Initialize Harvester
        logger.info("[4/5] AlphaHarvester Strategy engaged.")
        await self.harvester.oracle.load_model()'''
    if target_main in main_content:
        main_content = main_content.replace(target_main, replace_main)
        with open('src/main.py', 'w', encoding='utf-8') as f:
            f.write(main_content)
        print("? main.py patched")

    # 2. Patch harvester to inject oracle
    with open('src/strategy/alpha_harvester.py', 'r', encoding='utf-8') as f:
        harv_content = f.read()

    target_harv = '''        from src.alpha.alpha_scorer import AlphaScorer
        self.scorer = AlphaScorer()'''
    replace_harv = '''        from src.alpha.alpha_scorer import AlphaScorer
        self.scorer = AlphaScorer(oracle=self.oracle)'''
    if target_harv in harv_content:
        harv_content = harv_content.replace(target_harv, replace_harv)
        with open('src/strategy/alpha_harvester.py', 'w', encoding='utf-8') as f:
            f.write(harv_content)
        print("? alpha_harvester.py patched")

if __name__ == '__main__':
    patch_main_and_harvester()
