import re

with open('src/core/alpha.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''            return Signal(
                direction=signal_dir,
                conviction_score=conviction,
                implied_volatility=0.0,
                initial_invalidation_level=0.0,
                regime=regime,
                action=action,
                probability=1.0,
                mtf_volume_confirmed=True,
                atr=m15_atr_val / 1e-5 if m15_atr_val else 20.0,
                dynamic_target=poc
            )'''

replacement = '''            return Signal(
                direction=signal_dir,
                conviction_score=conviction,
                implied_volatility=0.0,
                initial_invalidation_level=0.0,
                regime=regime,
                action=action,
                probability=1.0,
                mtf_volume_confirmed=True,
                atr=m15_atr_val / 1e-5 if m15_atr_val else 20.0,
                dynamic_target=poc,
                is_hyper_scale=is_hyper_scale
            )'''

if target in content:
    content = content.replace(target, replacement)
    with open('src/core/alpha.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched Signal return in alpha.py")
else:
    print("Target not found.")

