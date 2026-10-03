$Content = [IO.File]::ReadAllText("src/web/templates/index.html", [System.Text.Encoding]::UTF8)

$Content = [regex]::Replace($Content, '(?s)<button id="btn-force-buy".*?</button>', @
"
            <button id="btn-force-buy" class="flex flex-col items-center justify-center w-full py-4 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg shadow-lg shadow-emerald-900/50 transition-all active:scale-95">
                <span class="text-sm">[FORCE BUY]</span>
                <span class="text-xs text-emerald-200 mt-1 font-normal">บังคับเปิดไม้ Buy ทันที</span>
            </button>
"@)

$Content = [regex]::Replace($Content, '(?s)<button id="btn-force-sell".*?</button>', @
"
            <button id="btn-force-sell" class="flex flex-col items-center justify-center w-full py-4 bg-red-600 hover:bg-red-500 text-white font-bold rounded-lg shadow-lg shadow-red-900/50 transition-all active:scale-95">
                <span class="text-sm">[FORCE SELL]</span>
                <span class="text-xs text-red-200 mt-1 font-normal">บังคับเปิดไม้ Sell ทันที</span>
            </button>
"@)

$Content = [regex]::Replace($Content, '(?s)<button onclick="sendCommand\('HARVEST_ALL\\)'".*?</button>', @
"
            <button onclick="sendCommand('HARVEST_ALL')" class="flex flex-col items-center justify-center w-full py-4 mt-4 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg transition-all active:scale-95 shadow-lg shadow-blue-900/50">
                <span class="text-sm">[HARVEST ALL]</span>
                <span class="text-xs text-blue-200 mt-1 font-normal">ปิดทุกไม้ เก็บกาไรเข้าพอร์ิ</span>
            </button>
"@)

$Content = [regex]::Replace($Content, '(?s)<button onclick="sendCommand\('CHOP_50\')".*?</button>', @
"
            <button onclick="sendCommand('CHOP_50')" class="flex flex-col items-center justify-center w-full py-4 bg-orange-600 hover:bg-orange-500 text-white font-bold rounded-lg transition-all active:scale-95 shadow-lg shadow-orange-900/50">
                <span class="text-sm">[CHOP 50%]</span>
                <span class="text-xs text-orange-200 mt-1 font-normal">หั่นไม้ที่ขาดทุนทิ้ง 50%
                </span>
            </button>
"@)

$Content = [regex]::Replace($Content, '(?s)<button onclick="openEODReport\(\)".*?</button>', @
"
            <button onclick="openEODReport()" class="flex flex-col items-center justify-center w-full py-4 mt-4 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-lg transition-all active:scale-95 shadow-lg shadow-indigo-900/50">
                <span class="text-sm">[EOD QUANT REPORT]</span>
                <span class="text-xs text-indigo-200 mt-1 font-normal">สรุปสถิติการเทรดประจำวัน</span>
            </button>
"@)

$Content = [regex]::Replace($Content, '(?s)<button onclick="sendCommand\('PANIC_HALT\\)"'.*?</button>', @
"
                <button onclick="sendCommand('PANIC_HALT')" class="flex flex-col items-center justify-center w-full py-6 bg-red-700 hover:bg-red-600 border-2 border-red-500 text-white font-black rounded-xl shadow-[0_0_20pxrgba(220,38,38,0.6)] transition-all active:scale-95 tracking-widest">
                    <span class="text-sm">[PANIC HALT]</span>
                    <span class="text-xs text-red-200 mt-1 font-normal tracking-normal">หยุดฉุกเฉินและปิดทุกออร์เดอร์</span>
                </button>
"@)

[IO.File]::WriteAllText("src/web/templates/index.html", $Content, [System.Text.Encoding]::UTF8)
