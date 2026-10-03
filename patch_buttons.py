import re

with open('src/web/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

force_buy_old = '''            <button id="btn-force-buy" class="w-full py-4 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg shadow-lg shadow-emerald-900/50 transition-all active:scale-95 text-sm">
                [FORCE BUY]
            </button>'''
force_buy_new = '''            <button id="btn-force-buy" class="flex flex-col items-center justify-center w-full py-4 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg shadow-lg shadow-emerald-900/50 transition-all active:scale-95">
                <span class="text-sm">[FORCE BUY]</span>
                <span class="text-xs text-emerald-200 mt-1 font-normal">บังคับเปิดไม้ Buy ทันที</span>
            </button>'''

force_sell_old = '''            <button id="btn-force-sell" class="w-full py-4 bg-red-600 hover:bg-red-500 text-white font-bold rounded-lg shadow-lg shadow-red-900/50 transition-all active:scale-95 text-sm">
                [FORCE SELL]
            </button>'''
force_sell_new = '''            <button id="btn-force-sell" class="flex flex-col items-center justify-center w-full py-4 bg-red-600 hover:bg-red-500 text-white font-bold rounded-lg shadow-lg shadow-red-900/50 transition-all active:scale-95">
                <span class="text-sm">[FORCE SELL]</span>
                <span class="text-xs text-red-200 mt-1 font-normal">บังคับเปิดไม้ Sell ทันที</span>
            </button>'''

harvest_all_old = '''            <button onclick="sendCommand('HARVEST_ALL')" class="w-full py-4 mt-4 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg transition-all active:scale-95 text-sm shadow-lg shadow-blue-900/50">
                [HARVEST ALL]
            </button>'''
harvest_all_new = '''            <button onclick="sendCommand('HARVEST_ALL')" class="flex flex-col items-center justify-center w-full py-4 mt-4 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg transition-all active:scale-95 shadow-lg shadow-blue-900/50">
                <span class="text-sm">[HARVEST ALL]</span>
                <span class="text-xs text-blue-200 mt-1 font-normal">ปิดทุกไม้ เก็บกำไรเข้าพอร์ต</span>
            </button>'''

chop_old = '''            <button onclick="sendCommand('CHOP_50')" class="w-full py-4 bg-orange-600 hover:bg-orange-500 text-white font-bold rounded-lg transition-all active:scale-95 text-sm shadow-lg shadow-orange-900/50">
                [CHOP 50%]
            </button>'''
chop_new = '''            <button onclick="sendCommand('CHOP_50')" class="flex flex-col items-center justify-center w-full py-4 bg-orange-600 hover:bg-orange-500 text-white font-bold rounded-lg transition-all active:scale-95 shadow-lg shadow-orange-900/50">
                <span class="text-sm">[CHOP 50%]</span>
                <span class="text-xs text-orange-200 mt-1 font-normal">หั่นไม้ที่ขาดทุนทิ้ง 50%</span>
            </button>'''

eod_old = '''            <button onclick="openEODReport()" class="w-full py-4 mt-4 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-lg transition-all active:scale-95 text-sm shadow-lg shadow-indigo-900/50">
                [EOD QUANT REPORT]
            </button>'''
eod_new = '''            <button onclick="openEODReport()" class="flex flex-col items-center justify-center w-full py-4 mt-4 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-lg transition-all active:scale-95 shadow-lg shadow-indigo-900/50">
                <span class="text-sm">[EOD QUANT REPORT]</span>
                <span class="text-xs text-indigo-200 mt-1 font-normal">สรุปสถิติการเทรดประจำวัน</span>
            </button>'''

panic_old = '''                <button onclick="sendCommand('PANIC_HALT')" class="w-full py-6 bg-red-700 hover:bg-red-600 border-2 border-red-500 text-white font-black rounded-xl shadow-[0_0_20px_rgba(220,38,38,0.6)] transition-all active:scale-95 tracking-widest text-sm">
                    [PANIC HALT]
                </button>'''
panic_new = '''                <button onclick="sendCommand('PANIC_HALT')" class="flex flex-col items-center justify-center w-full py-6 bg-red-700 hover:bg-red-600 border-2 border-red-500 text-white font-black rounded-xl shadow-[0_0_20px_rgba(220,38,38,0.6)] transition-all active:scale-95 tracking-widest">
                    <span class="text-sm">[PANIC HALT]</span>
                    <span class="text-xs text-red-200 mt-1 font-normal tracking-normal">หยุดฉุกเฉินและปิดทุกออเดอร์</span>
                </button>'''

content = content.replace(force_buy_old, force_buy_new)
content = content.replace(force_sell_old, force_sell_new)
content = content.replace(harvest_all_old, harvest_all_new)
content = content.replace(chop_old, chop_new)
content = content.replace(eod_old, eod_new)
content = content.replace(panic_old, panic_new)

with open('src/web/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

