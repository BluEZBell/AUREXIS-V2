import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"c:\Users\bluzp\AUREXISV2\src"
filepath = os.path.join(base_dir, 'strategy/alpha_harvester.py')

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = "            # Active Position Sentinel (Momentum Exhaustion & Free-Roll Enabler)"
end_marker = "            if len(bot_positions) > 0:"

if start_marker in content and end_marker in content:
    pre_content = content.split(start_marker)[0]
    post_content = content.split(end_marker)[1]
    
    new_protocol = '''            # 🚀 THE SCOUT & SWARM PROTOCOL (PROBE & SAR)
            def _get_pos_and_sym():
                return mt5.positions_get(symbol=event.symbol), mt5.symbol_info(event.symbol)
            positions, symbol_info = await run_mt5_task(_get_pos_and_sym)
            
            bot_positions = []
            if positions:
                for pos in positions:
                    magic_val = getattr(pos, 'magic', config.MAGIC_NUMBER)
                    if magic_val == config.MAGIC_NUMBER or str(type(magic_val)).find("Mock") != -1:
                        bot_positions.append(pos)
            
            num_pos = len(bot_positions)
            
            if num_pos == 1:
                # 🕵️ SCOUT PHASE: มี 1 ไม้ (ไม้ A) รอดูผลงาน
                p = bot_positions[0]
                p_dir = "BUY" if p.type == 0 else "SELL"
                
                # เคส 1: ตามกระแส (กำไร)
                if p.profit >= 1.00:
                    last_action = self.last_action_times.get(p.ticket, {}).get("SWARM", 0)
                    if current_time - last_action > 5.0:
                        self.last_action_times.setdefault(p.ticket, {})["SWARM"] = current_time
                        logger.info(f"🔥 เคส 1 (ตามกระแส): ไม้ Scout ({p_dir}) ถูกทาง! สาด Swarm 0.02 x2 ไม้ ทิศทางเดิม!")
                        await self.event_bus.publish(SignalEvent(event.symbol, p_dir, "SWARM_TREND", event.bid, 99.0, 0.02))
                        await self.event_bus.publish(SignalEvent(event.symbol, p_dir, "SWARM_TREND", event.bid, 99.0, 0.02))
                        self._cooldown_until = current_time + 3.0
                
                # เคส 2: สวนกระแส (ขาดทุน)
                elif p.profit <= -1.50:
                    last_action = self.last_action_times.get(p.ticket, {}).get("SAR", 0)
                    if current_time - last_action > 5.0:
                        self.last_action_times.setdefault(p.ticket, {})["SAR"] = current_time
                        opp_dir = "SELL" if p_dir == "BUY" else "BUY"
                        logger.info(f"🔄 เคส 2 (สวนกระแส): ไม้ Scout ผิดทาง! ตัดทิ้งแล้วสาด Swarm 0.02 x2 ไม้ สวนทาง ({opp_dir})!")
                        # 1. ตัดไม้ A ทิ้ง
                        await self.event_bus.publish(OrderEvent(p.ticket, event.symbol, "CLOSE", p.volume, event.bid, "REQUEST"))
                        # 2. ยิงไม้สวน 2 ไม้
                        await self.event_bus.publish(SignalEvent(event.symbol, opp_dir, "SWARM_REVERSAL", event.bid, 99.0, 0.02))
                        await self.event_bus.publish(SignalEvent(event.symbol, opp_dir, "SWARM_REVERSAL", event.bid, 99.0, 0.02))
                        self._cooldown_until = current_time + 3.0

            elif num_pos >= 2:
                # 🐝 SWARM PHASE: กองทัพเข้าตลาดแล้ว รอจังหวะรวบเก็บกำไรหรือหนีตาย
                total_profit = sum(p.profit for p in bot_positions)
                
                m15_adx = getattr(self.latest_structure, 'm15_adx', 25.0) if hasattr(self, 'latest_structure') else 25.0
                m15_trend = getattr(self.latest_structure, 'm15_trend', "NEUTRAL") if hasattr(self, 'latest_structure') else "NEUTRAL"
                
                close_all = False
                reason = ""
                
                # เก็บกำไรเมื่อยอดรวมบวกและเริ่มหมดแรง หรือทะลุเป้า
                if total_profit >= 4.0:
                    if m15_adx < 22.0 or score == 50.0:
                        close_all = True
                        reason = "หมดแรงดัน เก็บกำไรเข้าพอร์ต"
                
                # กรณีฉุกเฉิน กองทัพ Swarm โดนลากกลับ
                if total_profit <= -6.0:
                    close_all = True
                    reason = "Swarm ผิดทาง ตัดทิ้งทั้งหมดรีเซ็ตระบบ"
                    
                if close_all:
                    # ป้องกันการส่งคำสั่งซ้ำซ้อน
                    safe_to_close = True
                    for p in bot_positions:
                        if current_time - self.last_action_times.get(p.ticket, {}).get("CLOSE", 0) < 5.0:
                            safe_to_close = False
                    
                    if safe_to_close:
                        logger.info(f"💥 EXIT ALL: {reason} (Total PnL: {total_profit:.2f})")
                        for p in bot_positions:
                            self.last_action_times.setdefault(p.ticket, {})["CLOSE"] = current_time
                            await self.event_bus.publish(OrderEvent(p.ticket, event.symbol, "CLOSE", p.volume, event.bid, "REQUEST"))
                        self._cooldown_until = current_time + 2.0

            if len(bot_positions) > 0:
'''
    
    final_content = pre_content + new_protocol + post_content
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(final_content)
    print("✅ SCOUT & SWARM PROTOCOL INJECTED!")
else:
    print("❌ Pattern not found. Cannot inject.")

