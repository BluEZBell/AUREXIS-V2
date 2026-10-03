import os
filepath = r'C:\Users\bluzp\.gemini\antigravity\brain\241c23b7-6545-4835-9bd1-d145fc33b30c\Execution_Audit_Full.md'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

with open(filepath, 'w', encoding='utf-8') as f:
    f.write('# Full Execution Audit (After 2026-09-30 03:57:05)\n\n`	ext\n' + content + '\n`\n')
