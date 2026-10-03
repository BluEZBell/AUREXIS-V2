import asyncio
from src.core.campaign_ledger import CampaignLedger
from src.analytics.data_harvester import QuantDataHarvester
from src.core.event_bus import EventBus

import pytest

@pytest.mark.asyncio
async def test():
    eb = EventBus()
    cl = CampaignLedger(eb)
    await cl.initialize()
    ql = QuantDataHarvester(eb)
    await ql.initialize()
    print(f"CL freed: {await cl.perform_weekend_maintenance()}")
    print(f"QL freed: {await ql.perform_weekend_maintenance()}")

if __name__ == "__main__":
    asyncio.run(test())
