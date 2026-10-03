import os

def patch_cancel():
    bridge_path = 'src/execution/bridge.py'
    with open(bridge_path, 'r', encoding='utf-8') as f:
        br_content = f.read()

    cancel_target = '''                    def _cancel(o=ord):
                        req = {"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket}
                        mt5.order_send(req)
                    await run_mt5_task(_cancel)'''
                    
    cancel_replace = '''                    def _cancel(o=ord):
                        req = {"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket}
                        if getattr(config, 'DRY_RUN', False):
                            logger.warning(f"DRY RUN: Bypassing order cancel. Mocking success for req: {req}")
                            return
                        mt5.order_send(req)
                    await run_mt5_task(_cancel)'''

    if cancel_target in br_content:
        br_content = br_content.replace(cancel_target, cancel_replace)
        with open(bridge_path, 'w', encoding='utf-8') as f:
            f.write(br_content)
        print("? Added DRY_RUN to cancel order")

if __name__ == '__main__':
    patch_cancel()
