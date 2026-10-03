import re

with open('src/strategy/alpha_harvester.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''            if signal.conviction_score >= 50.0:
                logger.info(f"AlphaHarvester Execution Trace - Received Signal Score: {signal.conviction_score:.2f} Dir: {signal.direction}")

            if signal.conviction_score >= 65.0:
                logger.info(f"Micro-Breakout trigger evaluated. Conviction: {signal.conviction_score:.2f} | Regime: {signal.regime} | Requesting quota.")'''

replacement = '''            if signal.conviction_score >= 50.0:
                logger.info(f"AlphaHarvester Execution Trace - Received Signal Score: {signal.conviction_score:.2f} Dir: {signal.direction}")

            # Operation: HFT Aggression - Eradicate Conservative Hardcodes
            # Trust the dynamic conviction score emitted by AlphaScorer and AdaptiveTuner
            if signal.direction in ["BUY", "SELL"]:
                logger.info(f"Micro-Breakout trigger evaluated. Conviction: {signal.conviction_score:.2f} | Regime: {signal.regime} | Requesting quota.")'''

if target in content:
    content = content.replace(target, replacement)
    with open('src/strategy/alpha_harvester.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched conservative hardcodes in alpha_harvester.py")
else:
    print("Target not found.")

