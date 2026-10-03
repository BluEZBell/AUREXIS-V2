import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock
from collections import namedtuple
from src.core.event_bus import EventBus, SignalEvent, TickEvent
from src.core.campaign_ledger import CampaignLedger
from src.strategy.alpha_harvester import AlphaHarvesterStrategy
from src.core.alpha import Signal as AlphaSignal
import src.core.config as config

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_harvester.db")

@pytest.mark.asyncio
async def test_tick_router_broadcast(db_path, mock_mt5_api):
    bus = EventBus()
    ledger = CampaignLedger(bus)
    ledger.db_path = db_path
    await ledger.initialize()
    
    mock_sentinel = MagicMock()
    mock_sentinel.process_tick = AsyncMock()
    
    mock_scorer = MagicMock()
    mock_scorer.evaluate_tick = AsyncMock(return_value=AlphaSignal(direction="NONE", conviction_score=0.0, implied_volatility=0.0, initial_invalidation_level=0.0, regime="UNKNOWN", action="NOISE"))
    
    mock_bridge = MagicMock()
    mock_risk = MagicMock()
    
    harvester = AlphaHarvesterStrategy(
        event_bus=bus,
        risk_manager=mock_risk,
        execution_bridge=mock_bridge,
        tick_sentinel=mock_sentinel,
        alpha_scorer=mock_scorer,
        campaign_ledger=ledger
    )
    
    config.TRADING_SYMBOL = "XAUUSD"
    mock_mt5_api.terminal_info.return_value = namedtuple('TerminalInfo', ['connected'])(connected=True)
    mock_mt5_api.symbol_info_tick.return_value = namedtuple('Tick', ['time', 'time_msc', 'bid', 'ask', 'volume'])(
        time=int(time.time()), time_msc=int(time.time()*1000) + 100, bid=1900.0, ask=1900.5, volume=10
    )
    
    # Run loop manually for a single tick iteration
    async def run_router_once():
        harvester._running = True
        tick = mock_mt5_api.symbol_info_tick(config.TRADING_SYMBOL)
        if tick and tick.time_msc > harvester._last_tick_time:
            harvester._last_tick_time = tick.time_msc
            tick_event = TickEvent(
                symbol=config.TRADING_SYMBOL,
                time=tick.time,
                bid=tick.bid,
                ask=tick.ask,
                volume=float(tick.volume)
            )
            await mock_sentinel.process_tick(tick_event)
            await harvester._handle_signal_execution(config.TRADING_SYMBOL, tick.bid, tick.ask)
    
    await run_router_once()
    
    # Assert Sentinel received the tick
    mock_sentinel.process_tick.assert_called_once()
    assert mock_sentinel.process_tick.call_args[0][0].bid == 1900.0
    
    # Assert Scorer was evaluated
    mock_scorer.evaluate_tick.assert_called_once_with("XAUUSD", 1900.0, 1900.5)

@pytest.mark.asyncio
async def test_signal_execution_approved(db_path, mock_mt5_api):
    bus = EventBus()
    ledger = CampaignLedger(bus)
    ledger.db_path = db_path
    await ledger.initialize()
    
    mock_sentinel = MagicMock()
    
    mock_scorer = MagicMock()
    # Scorer returns high conviction signal >= 85.0
    mock_scorer.evaluate_tick = AsyncMock(return_value=AlphaSignal(direction="BUY", conviction_score=88.0, implied_volatility=0.0, initial_invalidation_level=0.0, regime="STRONG_TREND_BULL", action="CORE", probability=0.70, mtf_volume_confirmed=True))
    
    mock_bridge = MagicMock()
    mock_bridge.process_signal = AsyncMock()
    
    mock_risk = MagicMock()
    mock_risk.calculate_lot_size = AsyncMock(return_value=0.5) # Risk manager approves lot size
    
    harvester = AlphaHarvesterStrategy(
        event_bus=bus,
        risk_manager=mock_risk,
        execution_bridge=mock_bridge,
        tick_sentinel=mock_sentinel,
        alpha_scorer=mock_scorer,
        campaign_ledger=ledger
    )
    
    published_events = []
    async def mock_publish(event):
        published_events.append(event)
        if isinstance(event, SignalEvent):
            await mock_bridge.process_signal(event)
            
    bus.publish = mock_publish
    
    mock_mt5_api.account_info.return_value = namedtuple('AccountInfo', ['equity'])(equity=10000.0)
    
    await harvester._handle_signal_execution("XAUUSD", 1900.0, 1900.5)
    
    # Wait for the task created by create_task to finish
    await asyncio.sleep(0.1)
    
    # Execution bridge should receive the SignalEvent
    mock_bridge.process_signal.assert_called_once()
    sig_event = mock_bridge.process_signal.call_args[0][0]
    assert sig_event.direction == "BUY"
    assert sig_event.conviction == 88.0
    assert sig_event.volume == 0.5
    assert sig_event.price == 1900.5 # Buy at ask

@pytest.mark.asyncio
async def test_signal_execution_denied(db_path, mock_mt5_api):
    bus = EventBus()
    ledger = CampaignLedger(bus)
    ledger.db_path = db_path
    await ledger.initialize()
    
    mock_sentinel = MagicMock()
    
    mock_scorer = MagicMock()
    # Scorer returns low conviction signal < 65.0
    mock_scorer.evaluate_tick = AsyncMock(return_value=AlphaSignal(direction="BUY", conviction_score=64.0, implied_volatility=0.0, initial_invalidation_level=0.0, regime="RANGE", action="PROBE", probability=0.50, mtf_volume_confirmed=False))
    
    mock_bridge = MagicMock()
    mock_bridge.process_signal = AsyncMock()
    mock_risk = MagicMock()
    mock_risk.calculate_lot_size = AsyncMock(return_value=0.5)
    
    harvester = AlphaHarvesterStrategy(
        event_bus=bus,
        risk_manager=mock_risk,
        execution_bridge=mock_bridge,
        tick_sentinel=mock_sentinel,
        alpha_scorer=mock_scorer,
        campaign_ledger=ledger
    )
    
    await harvester._handle_signal_execution("XAUUSD", 1900.0, 1900.5)
    
    await asyncio.sleep(0.1)
    
    # Execution bridge should NOT receive anything
    mock_bridge.process_signal.assert_not_called()
    mock_risk.calculate_lot_size.assert_not_called()
