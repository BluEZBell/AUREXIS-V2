import pytest
import asyncio
import time
import datetime
from unittest.mock import MagicMock, patch

import MetaTrader5 as mt5

from src.execution.bridge import MT5Bridge
from src.core.event_bus import EventBus, SignalEvent, TickEvent
from src.execution.risk_manager import RiskManager

@pytest.fixture
def event_bus():
    return EventBus()

@pytest.fixture
def risk_manager(event_bus):
    rm = RiskManager(event_bus, live_balance=1000.0)
    rm.calculate_sl_tp = MagicMock(return_value=(1.0, 1.5))
    return rm

@pytest.fixture
def bridge(event_bus, risk_manager):
    return MT5Bridge(event_bus, risk_manager)

@pytest.mark.asyncio
async def test_order_retry_logic(bridge):
    signal = SignalEvent(symbol="TEST", direction="BUY", strategy_id="STRAT1", price=100.0, conviction=95.0, volume=1.0)
    
    class MockSymbol:
        point = 0.0001
        volume_step = 0.01
        volume_min = 0.01
        volume_max = 100.0
        digits = 5
        filling_mode = 0
        trade_tick_size = 0.0001
        trade_tick_value = 1.0
        trade_contract_size = 100000.0
        swap_long = -1.0
        swap_short = -1.0
        spread = 20
    
    mock_symbol_info = MockSymbol()
    
    mock_tick = MagicMock()
    mock_tick.ask = 1.0500
    mock_tick.bid = 1.0498
    # Use a fixed safe time (e.g., 12:00:00 UTC) to avoid rollover shield
    mock_tick.time = 1716379200 # May 22, 2024 12:00:00 UTC
    
    mock_acc = MagicMock()
    mock_acc.margin_free = 10000.0
    mock_acc.equity = 10000.0
    
    # We want order_send to fail with CONNECTION twice, then succeed
    fail_res = MagicMock()
    fail_res.retcode = mt5.TRADE_RETCODE_CONNECTION
    
    success_res = MagicMock()
    success_res.retcode = mt5.TRADE_RETCODE_DONE
    success_res.order = 12345
    success_res.volume = 1.0
    success_res.price = 1.0500
    
    mock_order_send = MagicMock(side_effect=[fail_res, fail_res, success_res])
    
    with patch('src.execution.bridge.mt5.symbol_info', return_value=mock_symbol_info), \
         patch('src.execution.bridge.mt5.symbol_info_tick', return_value=mock_tick), \
         patch('src.execution.bridge.mt5.order_calc_margin', return_value=100.0), \
         patch('src.execution.bridge.mt5.account_info', return_value=mock_acc), \
         patch('src.execution.bridge.mt5.order_send', mock_order_send), \
         patch('src.execution.bridge.mt5.positions_get', return_value=[]), \
         patch('src.execution.bridge.config.DRY_RUN', False), \
         patch('asyncio.sleep') as mock_sleep:
             
        bridge._latest_m15_trend = "BULLISH"
        bridge._latest_h1_trend = "BULLISH"
        await bridge.process_signal(signal)
        
        # It should have called order_send 3 times
        assert mock_order_send.call_count == 3
        # It should have slept twice for 0.05 seconds
        assert mock_sleep.call_count >= 2
        mock_sleep.assert_any_call(0.05)
        
        # Verify deviation was set to 50
        last_request = mock_order_send.call_args[0][0]
        assert last_request['deviation'] == 50

@pytest.mark.asyncio
async def test_midnight_equity_reset(bridge):
    # Set initial state
    bridge._start_equity = 1000.0
    bridge._current_day = datetime.date(2023, 1, 1)
    bridge._panic_halt = True
    
    mock_acc = MagicMock()
    mock_acc.balance = 1050.0
    mock_acc.equity = 1100.0
    
    with patch('src.execution.bridge.mt5.account_info', return_value=mock_acc), \
         patch('src.execution.bridge.mt5.positions_get', return_value=[]), \
         patch('src.execution.bridge.datetime.datetime') as mock_datetime:
             
        # Mock current time to next day
        mock_dt_instance = MagicMock()
        mock_dt_instance.date.return_value = datetime.date(2023, 1, 2)
        mock_dt_instance.hour = 1
        mock_datetime.now.return_value.astimezone.return_value = mock_dt_instance
        
        # Call the broadcaster logic directly or simulate it
        # Actually start_position_broadcaster loops forever, let's just trigger one iteration manually by extracting the logic
        
        # Let's run a modified version or just patch asyncio.sleep to raise CancelledError
        async def dummy_sleep(*args, **kwargs):
            raise asyncio.CancelledError()
            
        with patch('asyncio.sleep', side_effect=dummy_sleep):
            await bridge.start_position_broadcaster()
            
        # Check resets
        assert bridge._start_equity == 1100.0
        assert bridge._current_day == datetime.date(2023, 1, 2)
        assert bridge._panic_halt is False

@pytest.mark.asyncio
async def test_live_candle_slicing(bridge):
    import numpy as np
    
    # Create 200 mock M15 candles
    dt = np.dtype([('time', '<i8'), ('open', '<f8'), ('high', '<f8'), ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<i8'), ('spread', '<i4'), ('real_volume', '<i8')])
    m15_rates = np.zeros(200, dtype=dt)
    m15_rates['open'] = 1.0050
    m15_rates['high'] = 1.0050
    m15_rates['low'] = 1.0050
    m15_rates['close'] = 1.0050
    
    # 199th candle (closed)
    m15_rates[-2]['open'] = 1.0000
    m15_rates[-2]['close'] = 1.0050
    m15_rates[-2]['high'] = 1.0050
    m15_rates[-2]['low'] = 1.0000
    
    # 200th candle (forming)
    m15_rates[-1]['open'] = 1.0060
    m15_rates[-1]['close'] = 1.0020 # Bearish forming
    m15_rates[-1]['high'] = 1.0060
    m15_rates[-1]['low'] = 1.0010
    
    h1_rates = np.zeros(200, dtype=dt)
    m5_rates = np.zeros(3, dtype=dt)
    m5_rates[-1]['open'] = 1.0060
    m5_rates[-1]['close'] = 1.0020
    
    with patch('src.execution.bridge.mt5.copy_rates_from_pos', side_effect=[m5_rates, m15_rates, h1_rates]), \
         patch('src.execution.bridge.mt5.symbol_info') as mock_sym, \
         patch('asyncio.sleep', side_effect=asyncio.CancelledError):
             
        mock_sym.return_value.point = 0.0001
        
        published_events = []
        async def mock_publish(event):
            published_events.append(event)
            
        bridge.event_bus.publish = mock_publish
        
        await bridge.start_structure_stream()
        
        assert len(published_events) > 0
        from src.core.event_bus import StructuralTrendEvent
        trend_events = [e for e in published_events if isinstance(e, StructuralTrendEvent)]
        assert len(trend_events) > 0
        event = trend_events[0]
        
        # Check that it evaluates the live forming candle for bullish/bearish
        # forming candle opened at 1.0050, closed at 1.0020 -> BEARISH
        assert event.m15_bearish_candle is True
        assert event.m15_bullish_candle is False
