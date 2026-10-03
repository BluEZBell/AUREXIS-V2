import asyncio
import json
import dataclasses
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

data = {
    "type": type(event).__name__,
    "data": dataclasses.asdict(event)
}

encoded = json.dumps(data)
print("Encoded:", encoded)

# parse it back
parsed = json.loads(encoded)
print("Parsed eurusd_val:", parsed['data']['eurusd_val'])
