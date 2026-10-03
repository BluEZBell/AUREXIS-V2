import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"c:\Users\bluzp\AUREXISV2\src"
filepath = os.path.join(base_dir, 'strategy/alpha_harvester.py')

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

bad_str = '''            score, loss_streak = result

            import time
            current_time = time.time()'''

good_str = '''            score, loss_streak = result

            import time
            current_time = time.time()
            if getattr(self, '_last_score_log', 0) == 0 or current_time - self._last_score_log > 60:
                logger.info(f"Current Bayesian Score: {score:.2f} (Loss Streak: {loss_streak})")
                self._last_score_log = current_time'''

if bad_str in content:
    content = content.replace(bad_str, good_str)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ SCORE LOGGING ADDED")
else:
    print("❌ PATTERN NOT FOUND IN ALPHA HARVESTER")
