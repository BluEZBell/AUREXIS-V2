import numpy as np
from src.core.config import setup_logger
logger = setup_logger("math_engine")

# COGNITIVE PILLAR 4: MT5 Wilder's Math
def calc_ema(prices, period):
    ema = np.zeros_like(prices)
    ema[0] = prices[0]
    alpha = 2.0 / (period + 1)
    for i in range(1, len(prices)):
        ema[i] = prices[i] * alpha + ema[i-1] * (1 - alpha)
    return ema

def calc_atr(highs, lows, closes, period=14):
    tr = np.zeros_like(closes)
    tr[0] = highs[0] - lows[0]
    for i in range(1, len(closes)):
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
    
    atr = np.zeros_like(closes)
    atr[period-1] = np.mean(tr[:period])
    alpha = 1.0 / period
    for i in range(period, len(closes)):
        atr[i] = tr[i] * alpha + atr[i-1] * (1 - alpha)
    return atr

def calc_rsi(prices, period=14):
    deltas = np.diff(prices)
    up = np.where(deltas > 0, deltas, 0)
    down = np.where(deltas < 0, -deltas, 0)
    
    avg_up = np.zeros_like(prices)
    avg_down = np.zeros_like(prices)
    
    avg_up[period] = np.mean(up[:period])
    avg_down[period] = np.mean(down[:period])
    
    alpha = 1.0 / period
    for i in range(period + 1, len(prices)):
        avg_up[i] = up[i-1] * alpha + avg_up[i-1] * (1 - alpha)
        avg_down[i] = down[i-1] * alpha + avg_down[i-1] * (1 - alpha)
        
    rs = np.divide(avg_up, avg_down, out=np.zeros_like(avg_up), where=avg_down!=0)
    rsi = np.where(avg_down == 0, 100.0, 100.0 - (100.0 / (1.0 + rs)))
    rsi[:period] = 50.0
    return rsi

def calc_recent_swing_high_low(highs, lows):
    if len(highs) < 5 or len(lows) < 5:
        return np.max(highs), np.min(lows)
        
    swing_high = np.max(highs[-5:])
    swing_low = np.min(lows[-5:])
    
    for i in range(len(highs) - 3, 1, -1):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            swing_high = highs[i]
            break
            
    for i in range(len(lows) - 3, 1, -1):
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            swing_low = lows[i]
            break
            
    return swing_high, swing_low
def calc_adx(highs, lows, closes, period=14):
    up_move = np.diff(highs)
    down_move = -np.diff(lows)
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    tr = np.zeros_like(closes)
    tr[0] = highs[0] - lows[0]
    for i in range(1, len(closes)):
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
    
    tr_smooth = np.zeros_like(closes)
    plus_di_smooth = np.zeros_like(closes)
    minus_di_smooth = np.zeros_like(closes)
    
    tr_smooth[period] = np.mean(tr[1:period+1])
    plus_di_smooth[period] = np.mean(plus_dm[:period])
    minus_di_smooth[period] = np.mean(minus_dm[:period])
    
    alpha = 1.0 / period
    for i in range(period + 1, len(closes)):
        tr_smooth[i] = tr[i] * alpha + tr_smooth[i-1] * (1 - alpha)
        plus_di_smooth[i] = plus_dm[i-1] * alpha + plus_di_smooth[i-1] * (1 - alpha)
        minus_di_smooth[i] = minus_dm[i-1] * alpha + minus_di_smooth[i-1] * (1 - alpha)
        
    di_plus = np.divide(plus_di_smooth * 100, tr_smooth, out=np.zeros_like(tr_smooth), where=tr_smooth!=0)
    di_minus = np.divide(minus_di_smooth * 100, tr_smooth, out=np.zeros_like(tr_smooth), where=tr_smooth!=0)
    
    dx = np.divide(np.abs(di_plus - di_minus) * 100, di_plus + di_minus, out=np.zeros_like(tr_smooth), where=(di_plus+di_minus)!=0)
    
    adx = np.zeros_like(closes)
    adx[period*2 - 1] = np.mean(dx[period:period*2])
    
    for i in range(period*2, len(closes)):
        adx[i] = dx[i] * alpha + adx[i-1] * (1 - alpha)
        
    return adx

def calc_macd(prices, fast_period=12, slow_period=26, signal_period=9):
    fast_ema = calc_ema(prices, fast_period)
    slow_ema = calc_ema(prices, slow_period)
    macd_line = fast_ema - slow_ema
    signal_line = calc_ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calc_bollinger_bands(prices, period=20, std_dev=2.0):
    sma = np.zeros_like(prices)
    upper_band = np.zeros_like(prices)
    lower_band = np.zeros_like(prices)
    
    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1 : i + 1]
        sma[i] = np.mean(window)
        std = np.std(window, ddof=0)
        upper_band[i] = sma[i] + (std_dev * std)
        lower_band[i] = sma[i] - (std_dev * std)
        
    # Fill initial values with first calculated point
    if len(prices) >= period:
        sma[:period-1] = sma[period-1]
        upper_band[:period-1] = upper_band[period-1]
        lower_band[:period-1] = lower_band[period-1]
        
    return upper_band, sma, lower_band


def calc_bbw_and_slope(upper_band, lower_band, sma, period=5):
    bbw = np.zeros_like(sma)
    mask = sma != 0
    bbw[mask] = (upper_band[mask] - lower_band[mask]) / sma[mask]
    
    bbw_slope = np.zeros_like(bbw)
    for i in range(period, len(bbw)):
        bbw_slope[i] = (bbw[i] - bbw[i-period]) / period
        
    return bbw, bbw_slope

def detect_absorption(open, high, low, close, swing_level, is_upper_sweep):
    open = np.asarray(open)
    high = np.asarray(high)
    low = np.asarray(low)
    close = np.asarray(close)
    
    candle_size = high - low
    
    with np.errstate(divide='ignore', invalid='ignore'):
        if is_upper_sweep:
            sweep = high > swing_level
            top_wick = high - np.maximum(open, close)
            wick_ratio = np.where(candle_size > 0, top_wick / candle_size, 0)
            absorption = sweep & (wick_ratio > 0.6) & (close < swing_level)
        else:
            sweep = low < swing_level
            bottom_wick = np.minimum(open, close) - low
            wick_ratio = np.where(candle_size > 0, bottom_wick / candle_size, 0)
            absorption = sweep & (wick_ratio > 0.6) & (close > swing_level)
            
    return absorption

def calculate_volume_profile(closes, volumes, bins=50):
    if closes is None or volumes is None:
        return 0.0, 0.0, 0.0
        
    closes = np.asarray(closes)
    volumes = np.asarray(volumes)
    
    min_len = min(len(closes), len(volumes))
    if min_len == 0:
        return 0.0, 0.0, 0.0
        
    closes = closes[-min_len:]
    volumes = volumes[-min_len:]
        
    min_price = np.min(closes)
    max_price = np.max(closes)
    
    if min_price == max_price:
        return float(min_price), float(min_price), float(min_price)
        
    hist, bin_edges = np.histogram(closes, bins=bins, weights=volumes)
    total_vol = np.sum(hist)
    if total_vol == 0:
         return float(closes[-1]), float(max_price), float(min_price)
         
    poc_idx = np.argmax(hist)
    poc = (bin_edges[poc_idx] + bin_edges[poc_idx+1]) / 2.0
    
    # Calculate Value Area (70%)
    target_vol = total_vol * 0.70
    current_vol = hist[poc_idx]
    
    up_idx = poc_idx
    down_idx = poc_idx
    
    while current_vol < target_vol and (up_idx < bins - 1 or down_idx > 0):
        up_vol = hist[up_idx + 1] if up_idx < bins - 1 else -1
        down_vol = hist[down_idx - 1] if down_idx > 0 else -1
        
        if up_vol >= down_vol and up_vol != -1:
            up_idx += 1
            current_vol += up_vol
        elif down_vol > up_vol and down_vol != -1:
            down_idx -= 1
            current_vol += down_vol
        elif up_vol == -1 and down_vol != -1:
            down_idx -= 1
            current_vol += down_vol
        elif down_vol == -1 and up_vol != -1:
            up_idx += 1
            current_vol += up_vol
        else:
            break
            
    val = bin_edges[down_idx]
    vah = bin_edges[up_idx + 1]
    
    return float(poc), float(vah), float(val)
