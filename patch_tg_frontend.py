import re

with open('src/web/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add Telegram Setup button to Header
header_target = '''        <div class="flex items-center space-x-4">
            <div id="account-identity"'''

header_replace = '''        <div class="flex items-center space-x-4">
            <button onclick="openTelegramModal()" class="text-xs font-bold text-gray-300 bg-gray-800 hover:bg-gray-700 px-3 py-1 rounded-full border border-gray-600 transition-colors shadow-lg">
                ⚙️ Telegram Setup
            </button>
            <div id="account-identity"'''
            
content = content.replace(header_target, header_replace)

# 2. Add Modal and JS
modal_html = '''
    <!-- Telegram Setup Modal -->
    <div id="telegram-modal" class="fixed inset-0 bg-black bg-opacity-70 hidden flex items-center justify-center z-50">
        <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-[400px] shadow-2xl">
            <h2 class="text-xl font-bold text-emerald-400 mb-4 border-b border-gray-700 pb-2">Telegram Setup</h2>
            <div class="space-y-4">
                <div>
                    <label class="block text-sm text-gray-400 mb-1">Bot Token</label>
                    <input type="text" id="tg-bot-token" placeholder="1234567890:ABCdefGhIJKlmNoPQRstuVWxyz" class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500">
                </div>
                <div>
                    <label class="block text-sm text-gray-400 mb-1">Chat ID</label>
                    <input type="text" id="tg-chat-id" placeholder="-1001234567890" class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500">
                </div>
                <div id="tg-modal-error" class="text-red-400 text-xs hidden"></div>
                <div class="flex space-x-3 pt-2">
                    <button onclick="closeTelegramModal()" class="flex-1 py-2 bg-gray-700 hover:bg-gray-600 text-white font-bold rounded-lg transition-colors">Cancel</button>
                    <button id="btn-save-tg" onclick="saveTelegramConfig()" class="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg transition-colors shadow-lg shadow-emerald-900/50">Save & Test</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        function openTelegramModal() {
            document.getElementById('telegram-modal').classList.remove('hidden');
            document.getElementById('tg-modal-error').classList.add('hidden');
        }

        function closeTelegramModal() {
            document.getElementById('telegram-modal').classList.add('hidden');
        }

        async function saveTelegramConfig() {
            const botToken = document.getElementById('tg-bot-token').value;
            const chatId = document.getElementById('tg-chat-id').value;
            const btn = document.getElementById('btn-save-tg');
            const errorDiv = document.getElementById('tg-modal-error');
            
            if (!botToken || !chatId) {
                errorDiv.innerText = "Please fill in both fields.";
                errorDiv.classList.remove('hidden');
                return;
            }
            
            btn.disabled = true;
            btn.innerText = "Testing...";
            errorDiv.classList.add('hidden');
            
            try {
                const response = await fetch('/api/telegram-config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ bot_token: botToken, chat_id: chatId })
                });
                const data = await response.json();
                if (response.ok) {
                    closeTelegramModal();
                    if (typeof log === 'function') log("Telegram config saved & tested successfully.");
                } else {
                    errorDiv.innerText = data.error || "Failed to save or send test message.";
                    errorDiv.classList.remove('hidden');
                }
            } catch (err) {
                errorDiv.innerText = err.message;
                errorDiv.classList.remove('hidden');
            } finally {
                btn.disabled = false;
                btn.innerText = "Save & Test";
            }
        }
    </script>
</body>'''

content = content.replace('</body>', modal_html)

with open('src/web/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
