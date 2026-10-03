import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"c:\Users\bluzp\AUREXISV2\src"
filepath = os.path.join(base_dir, 'strategy/alpha_harvester.py')

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

bad_str = '''                        logger.info(f"🔥 เคส 1 (ตามกระแส): ไม้ Scout ({p_dir}) ถูกทาง! สาด Swarm 0.02 x3 ไม้ ทิศทางเดิม!")
                        await self.event_bus.publish(SignalEvent(event.symbol, p_dir, "SWARM_TREND", event.bid, 99.0, 0.02))
                        await self.event_bus.publish(SignalEvent(event.symbol, p_dir, "SWARM_TREND", event.bid, 99.0, 0.02))
                        await self.event_bus.publish(SignalEvent(event.symbol, p_dir, "SWARM_TREND", event.bid, 99.0, 0.02))'''

good_str = '''                        logger.info(f"🔥 เคส 1 (ตามกระแส): ไม้ Scout ({p_dir}) ถูกทาง! สาด Swarm 0.02 x3 ไม้ ทิศทางเดิม!")
                        await self.event_bus.publish(SignalEvent(event.symbol, p_dir, "SWARM_TREND", event.bid, 99.0, 0.02))
                        await asyncio.sleep(0.1)
                        await self.event_bus.publish(SignalEvent(event.symbol, p_dir, "SWARM_TREND", event.bid, 99.0, 0.02))
                        await asyncio.sleep(0.1)
                        await self.event_bus.publish(SignalEvent(event.symbol, p_dir, "SWARM_TREND", event.bid, 99.0, 0.02))'''

bad_str2 = '''                        # 2. ยิงไม้สวน 3 ไม้ (B, C, D)
                        await self.event_bus.publish(SignalEvent(event.symbol, opp_dir, "SWARM_REVERSAL", event.bid, 99.0, 0.02))
                        await self.event_bus.publish(SignalEvent(event.symbol, opp_dir, "SWARM_REVERSAL", event.bid, 99.0, 0.02))
                        await self.event_bus.publish(SignalEvent(event.symbol, opp_dir, "SWARM_REVERSAL", event.bid, 99.0, 0.02))'''

good_str2 = '''                        # 2. ยิงไม้สวน 3 ไม้ (B, C, D)
                        await self.event_bus.publish(SignalEvent(event.symbol, opp_dir, "SWARM_REVERSAL", event.bid, 99.0, 0.02))
                        await asyncio.sleep(0.1)
                        await self.event_bus.publish(SignalEvent(event.symbol, opp_dir, "SWARM_REVERSAL", event.bid, 99.0, 0.02))
                        await asyncio.sleep(0.1)
                        await self.event_bus.publish(SignalEvent(event.symbol, opp_dir, "SWARM_REVERSAL", event.bid, 99.0, 0.02))'''

if bad_str in content and bad_str2 in content:
    content = content.replace(bad_str, good_str)
    content = content.replace(bad_str2, good_str2)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ SLEEP ADDED TO SWARM")
else:
    print("❌ PATTERN NOT FOUND IN ALPHA HARVESTER")
