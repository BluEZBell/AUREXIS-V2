import re

with open('run_live.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_launch_run_live = '''        import webbrowser
        logger.info("Auto-launching Telemetry Web HUD at http://localhost:8080 for Fund Manager...")
        asyncio.create_task(asyncio.to_thread(webbrowser.open, "http://localhost:8080"))'''

new_launch_run_live = '''        async def _delayed_browser_launch(url: str, delay: float = 1.5) -> None:
            await asyncio.sleep(delay)
            import os, sys, subprocess
            try:
                if sys.platform == 'win32':
                    os.startfile(url)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', url])
                else:
                    subprocess.Popen(['xdg-open', url])
                logger.info(f"Successfully triggered OS-level browser launch for {url}")
            except Exception as e:
                logger.warning(f"Failed to launch browser natively: {e}")

        logger.info("Auto-launching Telemetry Web HUD at http://localhost:8080 for Fund Manager...")
        asyncio.create_task(_delayed_browser_launch("http://localhost:8080"))'''

content = content.replace(old_launch_run_live, new_launch_run_live)

with open('run_live.py', 'w', encoding='utf-8') as f:
    f.write(content)


with open('src/main.py', 'r', encoding='utf-8') as f:
    content_main = f.read()

old_launch_main = '''        import webbrowser
        logger.info("Auto-launching Telemetry Web HUD at http://localhost:8080 for Fund Manager...")
        asyncio.create_task(asyncio.to_thread(webbrowser.open, "http://localhost:8080"))'''

content_main = content_main.replace(old_launch_main, new_launch_run_live) # use the exact same block

with open('src/main.py', 'w', encoding='utf-8') as f:
    f.write(content_main)

