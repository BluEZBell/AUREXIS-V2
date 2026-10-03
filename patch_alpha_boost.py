import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"c:\Users\bluzp\AUREXISV2\src"
filepath = os.path.join(base_dir, 'strategy/alpha_harvester.py')

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Circuit Breaker
bad_cb = '''            if loss_streak >= 3 and current_time > getattr(self, '_cooldown_until', 0):
                logger.warning("🛑 PING-PONG CIRCUIT BREAKER TRIPPED! 3 losses in a row. Pausing for 15 minutes.")'''
good_cb = '''            if loss_streak >= 5 and current_time > getattr(self, '_cooldown_until', 0):
                logger.warning("🛑 PING-PONG CIRCUIT BREAKER TRIPPED! 5 losses in a row. Pausing for 15 minutes.")'''

# 2. Take Profit and ADX
bad_tp = '''                # เก็บกำไรเมื่อยอดรวมบวกและเริ่มหมดแรง
                if not close_all and total_profit >= 5.0:
                    if m15_adx < 22.0 or score == 50.0:
                        close_all = True
                        reason = "หมดแรงดัน เก็บกำไรเข้าพอร์ต"'''
good_tp = '''                # เก็บกำไรเมื่อยอดรวมบวกและเริ่มหมดแรง
                if not close_all and total_profit >= 15.0:
                    if m15_adx < 25.0 or score == 50.0:
                        close_all = True
                        reason = "หมดแรงดัน เก็บกำไรเข้าพอร์ต (+)"'''

# 3. Conviction Thresholds
bad_th = '''        buy_threshold = 75.0
        sell_threshold = 25.0'''
good_th = '''        buy_threshold = 70.0
        sell_threshold = 30.0'''

if bad_cb in content and bad_tp in content and bad_th in content:
    content = content.replace(bad_cb, good_cb)
    content = content.replace(bad_tp, good_tp)
    content = content.replace(bad_th, good_th)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ ALPHA HARVESTER UPDATED")
else:
    print("❌ PATTERNS NOT FOUND IN ALPHA HARVESTER")
