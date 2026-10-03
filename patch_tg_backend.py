import re

with open('src/core/telemetry_server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add route
route_target = "self.app.router.add_post('/api/command', self.handle_api_tactical)"
route_replace = "self.app.router.add_post('/api/command', self.handle_api_tactical)\n        self.app.router.add_post('/api/telegram-config', self.handle_telegram_config)"

content = content.replace(route_target, route_replace)

# 2. Add handle_telegram_config method
method_code = '''
    async def handle_telegram_config(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            bot_token = data.get('bot_token', '').strip()
            chat_id = data.get('chat_id', '').strip()
            
            if not bot_token or not chat_id:
                return web.json_response({"error": "Missing bot_token or chat_id"}, status=400)
                
            import dotenv
            import asyncio
            import src.core.config as config
            
            # Update memory
            config.TELEGRAM_BOT_TOKEN = bot_token
            config.TELEGRAM_CHAT_ID = chat_id
            
            # Persist to .env asynchronously
            def _save_env():
                dotenv.set_key('.env', 'TELEGRAM_BOT_TOKEN', bot_token)
                dotenv.set_key('.env', 'TELEGRAM_CHAT_ID', chat_id)
            await asyncio.to_thread(_save_env)
            
            # Broadcast test message asynchronously
            async def _send_test():
                try:
                    from src.core.broadcaster import TelegramBroadcaster
                    broadcaster = TelegramBroadcaster(bot_token=bot_token, chat_id=chat_id)
                    await broadcaster.start()
                    await broadcaster.broadcast("🟢 [AUREXIS V2] Telegram link established. HFT Engine standing by.")
                    await asyncio.sleep(2) # Give it time to flush
                    await broadcaster.stop()
                except Exception as e:
                    logger.error(f"Failed to send Telegram test message: {e}")
                    
            asyncio.create_task(_send_test())
            
            return web.json_response({"status": "Success"})
        except Exception as e:
            logger.error(f"Error in handle_telegram_config: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_api_tactical'''

content = content.replace("    async def handle_api_tactical", method_code)

with open('src/core/telemetry_server.py', 'w', encoding='utf-8') as f:
    f.write(content)
