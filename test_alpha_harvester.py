import pytest
import asyncio
from unittest.mock import MagicMock
from src.strategy.alpha_harvester import AlphaHarvesterStrategy
from src.core.event_bus import EventBus, TickEvent, OrderEvent, SignalEvent

class MockPosition:
    def __init__(self, type_val, profit, volume, price_open, ticket=1, magic=999):
        self.type = type_val
        self.profit = profit
        self.volume = volume
        self.price_open = price_open
        self.ticket = ticket
        self.magic = magic
        
    def __getattr__(self, name):
        # Allow checking for mock type in getattr
        if name == 'magic':
            return self.magic
        raise AttributeError(name)

@pytest.mark.asyncio
async def test_alpha_harvester_free_roll(monkeypatch):
    bus = EventBus()
    from src.core.campaign_ledger import CampaignLedger
    ledger = CampaignLedger(bus)
    mock_rm = MagicMock()
    mock_rm.halted = False
    async def mock_calculate_lot_size(*args, **kwargs):
        return 0.1
    mock_rm.calculate_lot_size = mock_calculate_lot_size
    mock_bridge = MagicMock()
    from unittest.mock import AsyncMock
    mock_bridge.process_signal = AsyncMock()
    mock_sentinel = MagicMock()
    mock_scorer = MagicMock()
    strategy = AlphaHarvesterStrategy(bus, mock_rm, mock_bridge, mock_sentinel, mock_scorer, ledger)
    
    # Mock MT5 info
    import src.core.config as config
    config.MAGIC_NUMBER = 999
    config.ALLOWED_SESSIONS = [{"start": "00:00", "end": "23:59"}]
    
    mock_sym_info = MagicMock()
    mock_sym_info.point = 0.0001
    
    def mock_positions(symbol):
        # 3 BUY positions, all in profit
        return [
            MockPosition(0, 10.0, 0.1, 1.1000, ticket=1),
            MockPosition(0, 7.0, 0.1, 1.1010, ticket=2),
            MockPosition(0, 5.0, 0.1, 1.1020, ticket=3),
        ]
        
    async def mock_run_mt5_task(func, *args, **kwargs):
        if hasattr(func, '__name__') and func.__name__ == '<lambda>':
            code = func.__code__.co_code
            # Since we can't easily parse lambda, we just mock both based on context or return something that has both
            # Wait, `alpha_harvester.py` line 401 calls: `sym_info = await run_mt5_task(lambda: mt5.symbol_info(event.symbol))`
            # line 316 calls: `positions = await run_mt5_task(lambda: mt5.positions_get(symbol=config.TRADING_SYMBOL))`
            # We can inspect the caller or just return a smart mock object that works as both.
            import inspect
            source = inspect.getsource(func)
            if 'symbol_info' in source:
                return mock_sym_info
            elif 'positions_get' in source:
                return mock_positions("EURUSD")
            return mock_positions("EURUSD"), mock_sym_info
        return None
        
    monkeypatch.setattr("src.strategy.alpha_harvester.run_mt5_task", mock_run_mt5_task)
    
    # Mock get_indicators to return strong buy signal
    async def mock_evaluate_tick(symbol, bid, ask):
        from src.core.alpha import Signal
        return Signal(direction="BUY", conviction_score=95.0, implied_volatility=0.001, initial_invalidation_level=1.100, regime="STRONG_TREND_BULL", action="CORE", probability=0.9, mtf_volume_confirmed=True, dynamic_target=1.1100)
        
    monkeypatch.setattr(mock_scorer, "evaluate_tick", mock_evaluate_tick)
    
    published_events = []
    async def mock_publish(event):
        published_events.append(event)
        if isinstance(event, SignalEvent):
            await mock_bridge.process_signal(event)
            
    monkeypatch.setattr(bus, "publish", mock_publish)
    
    ledger.db_path = "test_freeroll.db"
    await ledger.initialize()
    cycle = await ledger.start_cycle(1, "BUY")
    cycle.state = "SCOUT_ACTIVE"
    cycle.probe_ticket = 1
    cycle.set_tickets = [2, 3]
    cycle.cycle_pnl = 20.0
    await ledger.save_cycle(cycle)
    
    # Send tick
    import time
    tick = TickEvent("EURUSD", 1.1050, 1.1051, time.time())
    await strategy._handle_signal_execution(tick.symbol, tick.bid, tick.ask)
    
    await asyncio.sleep(0.1)
    
    # The last position has 5.0 profit (norm_pnl = 5.0 / 0.1 * 0.1 = 5.0)
    # So it should open a 4th position if free-roll is implemented correctly
    assert mock_bridge.process_signal.called, "Should have opened a new position in free-roll"

@pytest.mark.asyncio
async def test_alpha_harvester_exhaustion(monkeypatch):
    bus = EventBus()
    from src.core.campaign_ledger import CampaignLedger
    ledger = CampaignLedger(bus)
    mock_rm = MagicMock()
    mock_rm.halted = False
    async def mock_calculate_lot_size(*args, **kwargs):
        return 0.1
    mock_rm.calculate_lot_size = mock_calculate_lot_size
    mock_bridge = MagicMock()
    from unittest.mock import AsyncMock
    mock_bridge.process_signal = AsyncMock()
    mock_sentinel = MagicMock()
    mock_scorer = MagicMock()
    strategy = AlphaHarvesterStrategy(bus, mock_rm, mock_bridge, mock_sentinel, mock_scorer, ledger)
    import src.core.config as config
    config.MAGIC_NUMBER = 999
    config.ALLOWED_SESSIONS = [{"start": "00:00", "end": "23:59"}]
    
    mock_sym_info = MagicMock()
    mock_sym_info.point = 0.0001
    
    def mock_positions(symbol):
        # 1 BUY position in profit
        return [
            MockPosition(0, 5.0, 0.1, 1.1000, ticket=1)
        ]
        
    async def mock_run_mt5_task(func, *args, **kwargs):
        if hasattr(func, '__name__') and func.__name__ == '<lambda>':
            import inspect
            source = inspect.getsource(func)
            if 'symbol_info' in source:
                return mock_sym_info
            elif 'positions_get' in source:
                return mock_positions("EURUSD")
            return mock_positions("EURUSD"), mock_sym_info
        return None
        
    monkeypatch.setattr("src.strategy.alpha_harvester.run_mt5_task", mock_run_mt5_task)
    
    # Mock get_indicators to return WEAK buy signal, STRONG sell signal -> exhaustion
    async def mock_evaluate_tick(symbol, bid, ask):
        from src.core.alpha import Signal
        return Signal(direction="SELL", conviction_score=95.0, implied_volatility=0.001, initial_invalidation_level=1.110, regime="EXHAUSTION", action="EXHAUSTION")
    monkeypatch.setattr(mock_scorer, "evaluate_tick", mock_evaluate_tick)
    
    published_events = []
    async def mock_publish(event):
        published_events.append(event)
        
    monkeypatch.setattr(bus, "publish", mock_publish)
    ledger.db_path = "test_exhaustion.db"
    await ledger.initialize()
    cycle = await ledger.start_cycle(1, "BUY")
    cycle.state = "SCOUT_ACTIVE"
    cycle.probe_ticket = 1
    await ledger.save_cycle(cycle)

    import time
    tick = TickEvent("EURUSD", 1.1020, 1.1021, time.time())
    await strategy._handle_signal_execution(tick.symbol, tick.bid, tick.ask)
    
    await asyncio.sleep(0.1)
    
    # Check if OrderEvent(CLOSE) was published due to exhaustion
    assert any(isinstance(e, OrderEvent) and e.direction == "CLOSE" for e in published_events), "Should have closed on exhaustion"

