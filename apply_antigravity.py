import os
import re

BASE_DIR = r"c:\Users\bluzp\AUREXISV2\src"

def patch_file(filepath, pattern, replacement, flags=re.MULTILINE | re.DOTALL):
    full_path = os.path.join(BASE_DIR, filepath)
    if not os.path.exists(full_path):
        print(f"X File not found: {full_path}")
        return
        
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    new_content = re.sub(pattern, replacement, content, flags=flags)
    
    if content != new_content:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"V Patched: {filepath}")
    else:
        print(f"! Skipped (no changes / already patched / pattern not found): {filepath}")

# 1. bridge.py (Execution)
patch_file('execution/bridge.py',
           r'acc_info\.margin_free \* 0\.85',
           r'acc_info.margin_free * 0.95')

patch_file('execution/bridge.py',
           r'spacing = 120\.0 \* point',
           r'spacing = 80.0 * point if getattr(signal, "conviction", 50.0) >= 80.0 or getattr(signal, "conviction", 50.0) <= 20.0 else 120.0 * point')

# 2. alpha_harvester.py
patch_file('strategy/alpha_harvester.py',
           r'momentum_dead = False\s*# เทรนด์ตายเมื่อ ADX ร่วง < 18.*?if momentum_dead and pos\.profit >= 1\.5 \* \(pos\.volume / 0\.01\):',
           r'''momentum_dead = False
                        is_ranging = m15_adx < 22.0
                        
                        # 1. พลิกวิกฤตไซด์เวย์ (Range Scalping): เก็บกำไรเร็วเพื่อรีไซเคิล Margin กลับมา
                        if is_ranging and pos.profit >= 1.5 * (pos.volume / 0.01):
                            momentum_dead = True
                            
                        # 2. รันเทรนด์ระดับสถาบัน (Snowball): ถือจนสุด แต่ถ้า Macro DXY/Yield ยังดันอยู่ ห้ามปิดหมู!
                        elif not is_ranging:
                            if (pos_dir == "BUY" and score <= 45.0) or (pos_dir == "SELL" and score >= 55.0):
                                momentum_dead = True
                            if (pos_dir == "BUY" and m15_z > 2.5 and score < 65.0) or (pos_dir == "SELL" and m15_z < -2.5 and score > 35.0):
                                momentum_dead = True
                                
                        if momentum_dead and pos.profit >= 0.5:''')

patch_file('strategy/alpha_harvester.py',
           r'pos\.profit <= -1\.50 \* \(pos\.volume / 0\.01\):',
           r'pos.profit <= -2.50 * (pos.volume / 0.01):')

patch_file('strategy/alpha_harvester.py',
           r'if not is_reversal and current_time < self\._cooldown_until:',
           r'if not is_reversal and not (score >= 80.0 or score <= 20.0) and current_time < self._cooldown_until:')

patch_file('strategy/alpha_harvester.py',
           r'self\._cooldown_until = current_time \+ 5\.0',
           r'self._cooldown_until = current_time + 1.0')

# 3. bayesian_scorer.py
patch_file('strategy/bayesian_scorer.py',
           r'# Smart Trend-Aware Dampening \(Stop Blocking Real Trends\)\s+original_score = score\s+# Dampen BUY',
           r'''# Smart Trend-Aware Dampening (Stop Blocking Real Trends)
        original_score = score
        
        # 🚀 [ANTIGRAVITY] ถ้า ADX (แรงสถาบัน) สูงกว่า 28 ห้ามกดคะแนนเด็ดขาด ปล่อยทะลุเพดานเพื่อรันเทรนด์ยาว!
        if m15_adx >= 28.0:
            return max(0.0, min(100.0, score))
            
        # Dampen BUY''')

# 4. sentinel.py (Execution)
patch_file('execution/sentinel.py',
           r'elif profit_points >= 120\.0:.*?\n\s+true_be = self\.risk_manager\.calculate_true_breakeven\(symbol_info, pos\.price_open, direction\)\n\s+if direction == "BUY":\n\s+true_be = max\(true_be, pos\.price_open \+ \(10\.0 \* point\)\)',
           r'''elif profit_points >= 140.0:
                true_be = self.risk_manager.calculate_true_breakeven(symbol_info, pos.price_open, direction)
                if direction == "BUY":
                    true_be = max(true_be, pos.price_open + (15.0 * point))''')

patch_file('execution/sentinel.py',
           r'true_be = min\(true_be, pos\.price_open - \(10\.0 \* point\)\)',
           r'true_be = min(true_be, pos.price_open - (15.0 * point))')

print("Initiating ANTIGRAVITY Protocol: The  to  Sprint...")
print("ALL SYSTEMS READY. RESTART THE BOT.")
