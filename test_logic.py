class MockSymbolInfo:
    def __init__(self, point, trade_stops_level):
        self.point = point
        self.trade_stops_level = trade_stops_level

class MockTick:
    def __init__(self, bid, ask):
        self.bid = bid
        self.ask = ask

class MockPosition:
    def __init__(self, type_val, price_open, sl, profit):
        self.type = type_val
        self.price_open = price_open
        self.sl = sl
        self.profit = profit
        self.symbol = "TEST"
        self.ticket = 1

def sweep_mock(pos, direction, tick, symbol_info):
    point = symbol_info.point
    stops_level = symbol_info.trade_stops_level * point + (10.0 * point)
    current_price = tick.bid if direction == "BUY" else tick.ask
    profit_points = (current_price - pos.price_open) / point if direction == "BUY" else (pos.price_open - current_price) / point

    new_sl = None
    reason = ""

    if profit_points > 400.0:
        trail_sl = current_price - (200.0 * point) if direction == "BUY" else current_price + (200.0 * point)
        if pos.sl == 0.0 or (direction == "BUY" and trail_sl > pos.sl) or (direction == "SELL" and trail_sl < pos.sl):
            new_sl = trail_sl
            reason = "Dynamic Trailing"
    elif pos.profit > 5.0 and pos.sl == 0.0:
        new_sl = pos.price_open + 0.00020 if direction == "BUY" else pos.price_open - 0.00020
        reason = "True Break-Even"

    if new_sl is not None:
        distance = abs(current_price - new_sl)
        if distance <= stops_level:
            return "Bypass", new_sl, distance, stops_level
        return "Modify", new_sl, distance, stops_level
    return "None", None, None, None

symbol_info = MockSymbolInfo(0.0001, 30)
# BUY
pos = MockPosition("BUY", 1.0000, 0.0, 10.0)
tick = MockTick(1.0050, 1.0051) # profit = 50 pips = 500 points
print("BUY:", sweep_mock(pos, "BUY", tick, symbol_info))

# SELL
pos2 = MockPosition("SELL", 1.0050, 0.0, 10.0)
tick2 = MockTick(0.9999, 1.0000) # profit = 50 pips = 500 points
print("SELL:", sweep_mock(pos2, "SELL", tick2, symbol_info))
