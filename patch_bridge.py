import re

with open('src/execution/bridge.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''            req = await run_mt5_task(_execute_order)
            if req == "ROLLOVER_SHIELD_ERROR":
                await self._log_and_publish("SHIELD BLOCK: Rollover dead-zone active", "warning")
                return
            if req == "SPREAD_SHIELD_ERROR":
                await self._log_and_publish("SHIELD BLOCK: Spread exceeds Black Swan hard limit (100.0 pts), aborting entry", "warning")
                return
            if req == "MARGIN_SHIELD_ERROR":
                await self._log_and_publish("SHIELD BLOCK: Insufficient free margin", "warning")
                return
            if req == "RISK_SHIELD_ERROR":
                await self._log_and_publish("SHIELD BLOCK: Structural SL is too wide (exceeds max account risk)", "warning")
                return
            if not isinstance(req, dict):
                return'''

new_block = '''            req = await run_mt5_task(_execute_order)
            if not isinstance(req, dict):
                return'''

content = content.replace(old_block, new_block)

with open('src/execution/bridge.py', 'w', encoding='utf-8') as f:
    f.write(content)
