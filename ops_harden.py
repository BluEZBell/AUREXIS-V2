import os
import re

def harden_event_bus():
    eb_path = 'src/core/event_bus.py'
    with open(eb_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''                        def _handle_task_result(t: asyncio.Task, cb_name=callback.__name__):
                            try:
                                exc = t.exception()
                                if exc:
                                    logger.error(f"Error in subscriber {cb_name} for {event_type.__name__}: {exc}")
                            except asyncio.CancelledError:
                                pass'''

    replace = '''                        def _handle_task_result(t: asyncio.Task, cb_name=callback.__name__):
                            try:
                                exc = t.exception()
                                if exc:
                                    import traceback
                                    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                                    logger.error(f"Error in subscriber {cb_name} for {event_type.__name__}:\n{tb_str}")
                            except asyncio.CancelledError:
                                pass'''

    if target in content:
        content = content.replace(target, replace)
        with open(eb_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? event_bus.py patched")
    else:
        print("?? target not found in event_bus.py")

def harden_ledger():
    ledger_path = 'src/core/campaign_ledger.py'
    with open(ledger_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace all occurrences of del self.active_cycles[something] with self.active_cycles.pop(something, None)
    content = re.sub(r'del self\.active_cycles\[(.*?)\]', r'self.active_cycles.pop(\1, None)', content)

    # We also want to protect access like cycle = self.active_cycles[cycle_id] if not protected properly.
    # Actually, cycle = self.active_cycles.get(cycle_id) is safer.
    content = re.sub(r'cycle = self\.active_cycles\[(.*?)\]', r'cycle = self.active_cycles.get(\1)\n            if not cycle:\n                return', content)

    with open(ledger_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("? campaign_ledger.py patched")

if __name__ == '__main__':
    harden_event_bus()
    harden_ledger()
