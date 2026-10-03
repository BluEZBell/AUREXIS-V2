class DynamicParamStore:
    def __init__(self):
        pass

    def get_fallback_atr(self, symbol: str) -> float:
        import MetaTrader5 as mt5
        tick_info = mt5.symbol_info_tick(symbol)
        symbol_info = mt5.symbol_info(symbol)
        if tick_info and symbol_info and symbol_info.point > 0:
            spread_pts = (tick_info.ask - tick_info.bid) / symbol_info.point
            return spread_pts * 10.0
        if symbol_info and symbol_info.last > 0 and symbol_info.point > 0:
            return (symbol_info.last * 0.005) / symbol_info.point
        return 100.0

    def get_max_allowed_spread(self, atr_points: float) -> float:
        # e.g., max spread is 15% of ATR
        if atr_points and atr_points > 0:
            return atr_points * 0.15
        return 30.0

    def get_grid_spacing(self, atr_points: float, conviction_score: float, symbol: str = "UNKNOWN", equity: float = 1000.0) -> float:
        # Margin-Aware Micro-Gridding: scale purely dynamically based on ATR
        atr = atr_points if atr_points and atr_points > 0 else self.get_fallback_atr(symbol)
        return atr * 0.20

    def get_sl_bounds(self, atr_points: float, symbol: str = "UNKNOWN") -> tuple[float, float]:
        # Return (min_sl, max_sl) dynamically
        atr = atr_points if atr_points and atr_points > 0 else self.get_fallback_atr(symbol)
        return atr * 0.5, atr * 3.0
