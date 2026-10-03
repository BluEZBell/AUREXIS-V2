import os
import re

def patch_main():
    file_path = 'src/main.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Imports
    import_target = '''from src.strategy.alpha_harvester import AlphaHarvesterStrategy'''
    import_replace = '''from src.strategy.alpha_harvester import AlphaHarvesterStrategy
from src.api.dashboard import app
from src.core.config import WEB_PORT
import uvicorn'''
    if import_target in content:
        content = content.replace(import_target, import_replace)
        print("? Added imports to main.py")

    # 2. Boot sequence
    boot_target = '''        # 4. Initialize Harvester
        logger.info("[4/4] AlphaHarvester Strategy engaged.")
        self.running = True
        logger.info("AUREXIS System Online. Commencing Operations.")'''
    boot_replace = '''        # 4. Initialize Harvester
        logger.info("[4/5] AlphaHarvester Strategy engaged.")
        
        # 5. Initialize Web Dashboard
        logger.info(f"[5/5] Spinning up FastAPI Web Dashboard on port {WEB_PORT}...")
        web_config = uvicorn.Config(app=app, host="0.0.0.0", port=WEB_PORT, log_level="warning")
        self.web_server = uvicorn.Server(web_config)
        self.web_task = asyncio.create_task(self.web_server.serve())
        
        self.running = True
        logger.info("AUREXIS System Online. Commencing Operations.")'''
    if boot_target in content:
        content = content.replace(boot_target, boot_replace)
        print("? Added web server boot sequence")

    # Fix numbering of previous boot steps
    content = content.replace("[1/4]", "[1/5]")
    content = content.replace("[2/4]", "[2/5]")
    content = content.replace("[3/4]", "[3/5]")

    # 3. Shutdown
    shutdown_target = '''        logger.info("AUREXIS System Offline. Graceful Shutdown Complete.")'''
    shutdown_replace = '''        if hasattr(self, 'web_server'):
            logger.info("Shutting down FastAPI Web Dashboard...")
            self.web_server.should_exit = True
            
        logger.info("AUREXIS System Offline. Graceful Shutdown Complete.")'''
    if shutdown_target in content:
        content = content.replace(shutdown_target, shutdown_replace)
        print("? Added web server shutdown")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    patch_main()
