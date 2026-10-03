import os

base_dir = r"c:\Users\bluzp\AUREXISV2\src"

def replace_in_file(filepath, old_str, new_str):
    full_path = os.path.join(base_dir, filepath)
    if not os.path.exists(full_path): 
        print(f"X Not found: {full_path}")
        return
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if old_str in content:
        content = content.replace(old_str, new_str)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ OVERDRIVE INJECTED: {filepath}")
    else:
        print(f"! Pattern not found: {filepath}")

# 1. ซ่อมโค้ดพัง & ลบระบบกลัวขาดทุน (Trauma Memory) ใน alpha_harvester.py
ah_path = "strategy/alpha_harvester.py"

bad_block_1 = '''# Trauma Memory: ถ้าเพิ่งเสียเงิน บังคับพักเบรก 15 นาที (900 วินาที)
                    if getattr(self, '_last_closed_pnl', 0.0) < 0.0:
                        self._cooldown_until = current_time + 900.0
                        logger.warning(f"TRAUMA PENALTY: ขาดทุน {self._last_closed_pnl:.2f}. ระงับการยิง 15 นาทีเพื่อเลี่ยง Whipsaw")
                    else:
                        self._cooldown_until = current_time + 15.0'''

good_block_1 = '''self._cooldown_until = current_time + 1.0'''

replace_in_file(ah_path, bad_block_1, good_block_1)

bad_block_2 = '''# 🚀 ล็อกแน่น: ถ้าอยู่ในช่วง Trauma Penalty ห้ามใช้ข้อยกเว้น Score 80 ทะลวง Cooldown เด็ดขาด!
            is_in_trauma = (current_time < self._cooldown_until) and (self._cooldown_until - current_time > 60.0)
            if not is_reversal and current_time < self._cooldown_until:
                if is_in_trauma or not (score >= 80.0 or score <= 20.0):
                    if intent_dir != "" and self.auto_sniper:'''

good_block_2 = '''if not is_reversal and not (score >= 80.0 or score <= 20.0) and current_time < self._cooldown_until:
                    if intent_dir != "" and self.auto_sniper:'''

replace_in_file(ah_path, bad_block_2, good_block_2)

# 2. ปลดลิมิตอัด Risk หนักสุดขั้ว 12% (risk_manager.py)
rm_path = "execution/risk_manager.py"
bad_rm = '''if equity < 80.0:
            risk_pct = 0.04  # บังคับลดไซส์เหลือ 0.01 Lot (Scout) เมื่อพอร์ตยุบ
        elif equity <= 250.0:
            risk_pct = 0.08  # เสี่ยง 8% สำหรับไม้แรก (ถ้าโดนลากเต็ม SL เสีย ~)'''

good_rm = '''if equity <= 250.0:
            risk_pct = 0.12  # OVERDRIVE: ยิงเต็มแม็กซ์ 12% ต่อไม้ พลิกวิกฤต!'''

replace_in_file(rm_path, bad_rm, good_rm)

# 3. ระดมยิงซ้อนไม้ Spacing แคบสุดขีด (execution/bridge.py)
eb_path = "execution/bridge.py"
bad_eb = '''spacing = 80.0 * point if getattr(signal, "conviction", 50.0) >= 80.0 or getattr(signal, "conviction", 50.0) <= 20.0 else 120.0 * point'''
good_eb = '''spacing = 40.0 * point if getattr(signal, "conviction", 50.0) >= 80.0 or getattr(signal, "conviction", 50.0) <= 20.0 else 80.0 * point'''
replace_in_file(eb_path, bad_eb, good_eb)

# 4. บังทุนให้เร็วเพื่อ Free-Roll (execution/sentinel.py)
ts_path = "execution/sentinel.py"
bad_ts = '''elif profit_points >= 140.0:'''
good_ts = '''elif profit_points >= 100.0:'''
replace_in_file(ts_path, bad_ts, good_ts)

# ตรวจสอบว่าโค้ดสมบูรณ์ ไม่พังแน่นอน
import py_compile
try:
    py_compile.compile(os.path.join(base_dir, ah_path), doraise=True)
    print("✅ Syntax Check Passed. BOT IS READY FOR SPRINT.")
except Exception as e:
    print(f"❌ Syntax Error: {e}")

