import re

with open('src/strategy/alpha_harvester.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_exhaustion = '''            if signal.action == "EXHAUSTION" or signal.regime == "EXHAUSTION":
                from src.core.event_bus import OrderEvent
                logger.info(f"Exhaustion detected. Issuing CLOSE event for {symbol}.")
                close_event = OrderEvent(
                    ticket=0,
                    symbol=symbol,
                    direction="CLOSE",
                    volume=0.0,
                    price=bid,
                    status="REQUESTED"
                )
                asyncio.create_task(self.event_bus.publish(close_event))'''

new_exhaustion = '''            if signal.action == "EXHAUSTION" or signal.regime == "EXHAUSTION":
                from src.core.event_bus import OrderEvent
                logger.info(f"Exhaustion detected. Issuing CLOSE events for {symbol}.")
                open_positions = await run_mt5_task(lambda: mt5.positions_get(symbol=symbol))
                if open_positions:
                    for pos in open_positions:
                        close_event = OrderEvent(
                            ticket=pos.ticket,
                            symbol=symbol,
                            direction="CLOSE",
                            volume=pos.volume,
                            price=bid,
                            status="REQUEST"
                        )
                        asyncio.create_task(self.event_bus.publish(close_event))'''

content = content.replace(old_exhaustion, new_exhaustion)
with open('src/strategy/alpha_harvester.py', 'w', encoding='utf-8') as f:
    f.write(content)
