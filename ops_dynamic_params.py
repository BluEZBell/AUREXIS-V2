import os

def apply_hyper_drive():
    file_path = 'src/core/dynamic_params.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''    def get_grid_spacing(self, atr_points: float, conviction_score: float, symbol: str = "UNKNOWN") -> float:
        # Scale grid spacing dynamically based on ATR and inverse to conviction.
        # Higher conviction = tighter spacing, lower conviction = wider spacing.
        atr = atr_points if atr_points and atr_points > 0 else self.get_fallback_atr(symbol)
        # If conviction is 100, spacing is 15% of ATR. If conviction is 50, spacing is 30% of ATR.
        conviction_factor = max(1.0, (150.0 - conviction_score) / 100.0)
        spacing = atr * 0.15 * conviction_factor
        return spacing'''
        
    replace = '''    def get_grid_spacing(self, atr_points: float, conviction_score: float, symbol: str = "UNKNOWN", equity: float = 1000.0) -> float:
        # Scale grid spacing dynamically based on ATR and inverse to conviction.
        # Higher conviction = tighter spacing, lower conviction = wider spacing.
        atr = atr_points if atr_points and atr_points > 0 else self.get_fallback_atr(symbol)
        # If conviction is 100, spacing is 15% of ATR. If conviction is 50, spacing is 30% of ATR.
        conviction_factor = max(1.0, (150.0 - conviction_score) / 100.0)
        spacing = atr * 0.15 * conviction_factor
        
        # Hyper-Drive Compression for small accounts
        if equity < 500.0:
            spacing *= 0.5
            
        return max(spacing, 20.0)'''

    if target in content:
        content = content.replace(target, replace)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("? dynamic_params.py patched.")
    else:
        print("?? Target not found in dynamic_params.py")

if __name__ == '__main__':
    apply_hyper_drive()
