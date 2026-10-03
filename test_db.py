import asyncio
from src.execution.state_ledger import StateLedger

async def main():
    ledger = StateLedger("test_state.db")
    await ledger.initialize()
    ledger.update_ticket_state(12345, 999, 1.5, 2.5, True)
    await asyncio.sleep(0.5)
    records = await ledger.get_all_records()
    print("Records:", records)
    assert 12345 in records
    assert records[12345]['virtual_sl'] == 1.5
    assert records[12345]['virtual_tp'] == 2.5
    assert records[12345]['risk_recycled'] is True

asyncio.run(main())
