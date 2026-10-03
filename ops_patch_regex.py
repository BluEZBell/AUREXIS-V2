import os
import re

def patch_telemetry_regex():
    file_path = 'src/execution/telemetry.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace handle_order_close with handle_order and add handle_signal
    content = re.sub(
        r'    async def handle_order_close\(self, event: OrderEvent\):.*?await self\._queue\.put\(msg\)',
        '''    async def handle_order(self, event: OrderEvent):
        if event.direction == "CLOSE":
            msg = f"??? <b>Order Liquidated</b>\\nTicket: {event.ticket}\\nCycle ID: {event.cycle_id}\\nPrice: {event.price:.5f}\\nStatus: {event.status}"
            await self._queue.put(msg)
        else:
            msg = f"? <b>Order Executed</b>\\nTicket: {event.ticket}\\nCycle ID: {event.cycle_id}\\nDirection: {event.direction}\\nStatus: {event.status}"
            await self._queue.put(msg)

    async def handle_signal(self, event: SignalEvent):
        msg = f"?? <b>Scout/Swarm Triggered</b>\\nDirection: {event.direction}\\nRegime: {event.regime}\\nConviction: {event.score:.2f}"
        await self._queue.put(msg)''',
        content,
        flags=re.DOTALL
    )

    # Add /status command
    content = re.sub(
        r'(await self\._queue\.put\(".*?PANIC HALT INITIATED.*?"\))',
        r'\1\n                                        elif text.lower() == "/status":\n                                            logger.info("TELEGRAM COMMAND: STATUS REPORT REQUESTED!")\n                                            await self.event_bus.publish(CommandEvent(action="STATUS_REPORT"))',
        content
    )

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("? telemetry.py regex patched")

if __name__ == '__main__':
    patch_telemetry_regex()
