import re

with open('run_live.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_launch_run_live = '''        self.telemetry_server.strategy = self.strategy
                
        # Blocking wait - kept alive entirely by the native asyncio loop running AlphaHarvester
        await self.strategy.start()'''

new_launch_run_live = '''        self.telemetry_server.strategy = self.strategy
                
        import webbrowser
        logger.info("Auto-launching Telemetry Web HUD at http://localhost:8080 for Fund Manager...")
        asyncio.create_task(asyncio.to_thread(webbrowser.open, "http://localhost:8080"))

        # Blocking wait - kept alive entirely by the native asyncio loop running AlphaHarvester
        await self.strategy.start()'''

content = content.replace(old_launch_run_live, new_launch_run_live)

with open('run_live.py', 'w', encoding='utf-8') as f:
    f.write(content)


with open('src/main.py', 'r', encoding='utf-8') as f:
    content_main = f.read()

old_launch_main = '''        task_s = asyncio.create_task(sentinel.start())
        bg_tasks.add(task_s)
        
        # Start the continuous event-driven orchestrator
        await orchestrator.start()'''

new_launch_main = '''        task_s = asyncio.create_task(sentinel.start())
        bg_tasks.add(task_s)
        
        import webbrowser
        logger.info("Auto-launching Telemetry Web HUD at http://localhost:8080 for Fund Manager...")
        asyncio.create_task(asyncio.to_thread(webbrowser.open, "http://localhost:8080"))

        # Start the continuous event-driven orchestrator
        await orchestrator.start()'''

content_main = content_main.replace(old_launch_main, new_launch_main)

with open('src/main.py', 'w', encoding='utf-8') as f:
    f.write(content_main)

