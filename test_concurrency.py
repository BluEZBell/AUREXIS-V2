import asyncio
import time
from src.data.tick_vault import TickVault

async def main():
    vault = TickVault(batch_size=10, filename="test_ticks.csv")
    
    # Rapidly add enough ticks to trigger multiple flushes instantly
    for i in range(100):
        await vault.add_tick(time.time(), 1.0, 1.1, 0.1, 100)
        
    await asyncio.sleep(2)
    print("Done")

if __name__ == "__main__":
    asyncio.run(main())
