import os

def patch_telemetry():
    file_path = 'src/execution/telemetry.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Imports
    import_target = '''from src.core.event_bus import EventBus, OrderEvent, ErrorEvent, TargetHitEvent, SpikeDetectedEvent, ScoutFailEvent, CommandEvent'''
    import_replace = '''from src.core.event_bus import EventBus, OrderEvent, ErrorEvent, TargetHitEvent, SpikeDetectedEvent, ScoutFailEvent, CommandEvent, SignalEvent'''
    if import_target in content:
        content = content.replace(import_target, import_replace)
        print("? Added SignalEvent to imports")

    # 2. Subscriptions
    sub_target = '''        self.event_bus.subscribe(ErrorEvent, self.handle_error)
        self.event_bus.subscribe(OrderEvent, self.handle_order_close)'''
    sub_replace = '''        self.event_bus.subscribe(ErrorEvent, self.handle_error)
        self.event_bus.subscribe(OrderEvent, self.handle_order)
        self.event_bus.subscribe(SignalEvent, self.handle_signal)'''
    if sub_target in content:
        content = content.replace(sub_target, sub_replace)
        print("? Updated subscriptions")

    # 3. Handle Order & Signal
    handler_target = '''    async def handle_order_close(self, event: OrderEvent):
        # Notify on structural / time-decay kills or orphans which issue CLOSE
        if event.direction == "CLOSE":
            msg = f"??? <b>Order Liquidated</b>\\nTicket: {event.ticket}\\nCycle ID: {event.cycle_id}\\nPrice: {event.price:.5f}"
            await self._queue.put(msg)'''
    handler_replace = '''    async def handle_order(self, event: OrderEvent):
        if event.direction == "CLOSE":
            msg = f"??? <b>Order Liquidated</b>\\nTicket: {event.ticket}\\nCycle ID: {event.cycle_id}\\nPrice: {event.price:.5f}\\nStatus: {event.status}"
            await self._queue.put(msg)
        else:
            msg = f"? <b>Order Executed</b>\\nTicket: {event.ticket}\\nCycle ID: {event.cycle_id}\\nDirection: {event.direction}\\nStatus: {event.status}"
            await self._queue.put(msg)

    async def handle_signal(self, event: SignalEvent):
        msg = f"?? <b>Scout/Swarm Triggered</b>\\nDirection: {event.direction}\\nRegime: {event.regime}\\nConviction: {event.score:.2f}"
        await self._queue.put(msg)'''
    if handler_target in content:
        content = content.replace(handler_target, handler_replace)
        print("? Updated order and signal handlers")

    # 4. Status command
    cmd_target = '''                                        if text.lower() in ["/panic", "/halt"]:
                                            logger.critical("TELEGRAM COMMAND: PANIC HALT RECEIVED!")
                                            await self.event_bus.publish(CommandEvent(action="PANIC_HALT"))
                                            await self._queue.put("?? PANIC HALT INITIATED. Liquidating all positions and locking bridge.")'''
    cmd_replace = '''                                        if text.lower() in ["/panic", "/halt"]:
                                            logger.critical("TELEGRAM COMMAND: PANIC HALT RECEIVED!")
                                            await self.event_bus.publish(CommandEvent(action="PANIC_HALT"))
                                            await self._queue.put("?? PANIC HALT INITIATED. Liquidating all positions and locking bridge.")
                                        elif text.lower() == "/status":
                                            logger.info("TELEGRAM COMMAND: STATUS REPORT REQUESTED!")
                                            await self.event_bus.publish(CommandEvent(action="STATUS_REPORT"))'''
    if cmd_target in content:
        content = content.replace(cmd_target, cmd_replace)
        print("? Added /status command handler")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

def update_env_example():
    file_path = '.env.example'
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write("\\n# Phase 7: Telemetry\\nTELEGRAM_BOT_TOKEN=your_bot_token_here\\nTELEGRAM_CHAT_ID=your_chat_id_here\\n")
    print("? Updated .env.example")

if __name__ == '__main__':
    patch_telemetry()
    update_env_example()
