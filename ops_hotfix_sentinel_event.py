import os

def fix_sentinel_event():
    file_path = 'src/execution/sentinel.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target1 = "self.event_bus.subscribe(StructuralTrendEvent, self.handle_structural_trend)"
    replace1 = "self.event_bus.subscribe(StructuralTrendEvent, self._handle_structure)"
    
    target2 = '''    async def handle_structural_trend(self, event: StructuralTrendEvent):
        self._latest_m15_trend = event.m15_trend'''
    replace2 = '''    async def _handle_structure(self, event: StructuralTrendEvent):
        self._latest_m15_trend = getattr(event, "m15_trend", None)'''

    if target1 in content:
        content = content.replace(target1, replace1)
    if target2 in content:
        content = content.replace(target2, replace2)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("? Patch applied successfully: Renamed structural trend handler.")

if __name__ == '__main__':
    fix_sentinel_event()
