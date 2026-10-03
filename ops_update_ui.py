import os

def update_ui():
    file_path = 'src/web/templates/index.html'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Part 1: Add HTML Grid for Matrix metrics
    target1 = '''            <div class="grid grid-cols-4 gap-2 mb-2 text-xs font-mono text-center">
                <div class="bg-gray-800 p-2 rounded flex flex-col">
                    <span class="text-gray-500 mb-1">GOLD</span>
                    <span id="tele-gold" class="text-white font-bold">----.--</span>
                </div>
                <div class="bg-gray-800 p-2 rounded flex flex-col">
                    <span class="text-gray-500 mb-1">SPREAD</span>
                    <span id="tele-spread" class="text-white font-bold">--</span>
                </div>
                <div class="bg-gray-800 p-2 rounded flex flex-col">
                    <span class="text-gray-500 mb-1">H1 TREND</span>
                    <span id="tele-h1" class="text-gray-400 font-bold">--</span>
                </div>
                <div class="bg-gray-800 p-2 rounded flex flex-col">
                    <span class="text-gray-500 mb-1">M15 TREND</span>
                    <span id="tele-m15" class="text-gray-400 font-bold">--</span>
                </div>
            </div>'''
            
    replace1 = '''            <div class="grid grid-cols-4 gap-2 mb-2 text-xs font-mono text-center">
                <div class="bg-gray-800 p-2 rounded flex flex-col">
                    <span class="text-gray-500 mb-1">GOLD</span>
                    <span id="tele-gold" class="text-white font-bold">----.--</span>
                </div>
                <div class="bg-gray-800 p-2 rounded flex flex-col">
                    <span class="text-gray-500 mb-1">SPREAD</span>
                    <span id="tele-spread" class="text-white font-bold">--</span>
                </div>
                <div class="bg-gray-800 p-2 rounded flex flex-col">
                    <span class="text-gray-500 mb-1">H1 TREND</span>
                    <span id="tele-h1" class="text-gray-400 font-bold">--</span>
                </div>
                <div class="bg-gray-800 p-2 rounded flex flex-col">
                    <span class="text-gray-500 mb-1">M15 TREND</span>
                    <span id="tele-m15" class="text-gray-400 font-bold">--</span>
                </div>
            </div>
            
            <div class="grid grid-cols-3 gap-2 mb-4 text-xs font-mono text-center">
                <div class="bg-gray-800 p-2 rounded flex flex-col border border-gray-700">
                    <span class="text-gray-500 mb-1">ADX REGIME</span>
                    <span id="matrix-adx" class="text-blue-400 font-bold">--</span>
                </div>
                <div class="bg-gray-800 p-2 rounded flex flex-col border border-gray-700">
                    <span class="text-gray-500 mb-1">Z-SCORE</span>
                    <span id="matrix-zscore" class="text-purple-400 font-bold">--</span>
                </div>
                <div class="bg-gray-800 p-2 rounded flex flex-col border border-gray-700">
                    <span class="text-gray-500 mb-1">ATR (M15)</span>
                    <span id="matrix-atr" class="text-orange-400 font-bold">--</span>
                </div>
            </div>'''

    # Part 2: Add JS logic
    target2 = '''                if (data.data.latest_structural_trend) {
                    const tr = data.data.latest_structural_trend;'''
                    
    replace2 = '''                if (data.data.latest_strategy_state) {
                    const st = data.data.latest_strategy_state;
                    if (st.adx_m15 !== undefined && document.getElementById('matrix-adx')) {
                        document.getElementById('matrix-adx').innerText = st.adx_m15 < 22.0 ? 'RANGE' : 'TREND';
                    }
                    if (st.z_score !== undefined && document.getElementById('matrix-zscore')) {
                        document.getElementById('matrix-zscore').innerText = st.z_score.toFixed(2);
                    }
                    if (st.atr_m15 !== undefined && document.getElementById('matrix-atr')) {
                        document.getElementById('matrix-atr').innerText = st.atr_m15.toFixed(2);
                    }
                }
                
                if (data.data.latest_structural_trend) {
                    const tr = data.data.latest_structural_trend;'''

    if target1 in content:
        content = content.replace(target1, replace1)
        print("? HTML injected.")
    else:
        print("?? HTML target not found.")

    if target2 in content:
        content = content.replace(target2, replace2)
        print("? JS injected.")
    else:
        print("?? JS target not found.")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    update_ui()
