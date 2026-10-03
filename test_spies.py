import asyncio
import sys

async def main():
    try:
        from src.core.event_bus import MacroUpdateEvent
        event = MacroUpdateEvent(
            dxy=0.0,
            us10y=0.0,
            usdjpy=0.0,
            vix=0.0,
            xagusd=0.0,
            usdcnh=0.0,
            usoil=0.0,
            eurusd_val=1.1,
            us500_val=5000.0
        )
        print("dataclass works")
        
        from src.data.macro_spies import MacroSpyNetwork
        from src.core.event_bus import EventBus
        bus = EventBus()
        spy = MacroSpyNetwork(bus)
        print("MacroSpyNetwork initialized")
        print("Keys:", list(spy.spies.keys()))
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
