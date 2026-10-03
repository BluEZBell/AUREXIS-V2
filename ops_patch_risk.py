import os
import re

def patch_risk_manager():
    file_path = 'src/execution/risk_manager.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update signature to accept conviction
    sig_target = '''def calculate_lot_size(self, equity: float, atr: float = None, sl_points: float = None) -> float:'''
    sig_replace = '''def calculate_lot_size(self, equity: float, atr: float = None, sl_points: float = None, conviction: float = 1.0) -> float:'''
    content = content.replace(sig_target, sig_replace)

    # 2. Inject logging before return lot
    log_target = '''            lot = max(0.01, round(lot, 2))
            
        return lot'''
    
    # Wait, the end of the method is:
    #             lot = round(lot / step) * step
    #             lot = max(min_vol, min(lot, max_vol))
    #         else:
    #             dynamic_sl_points = atr * 1.5
    #             lot = (equity * risk_pct) / max(dynamic_sl_points, 1.0)
    #             lot = max(0.01, round(lot, 2))
    #             
    #         return lot
    
    # Let's replace the whole end section
    end_target = '''            lot = round(lot / step) * step
            lot = max(min_vol, min(lot, max_vol))
        else:
            dynamic_sl_points = atr * 1.5
            lot = (equity * risk_pct) / max(dynamic_sl_points, 1.0)
            lot = max(0.01, round(lot, 2))
            
        return lot'''
        
    end_replace = '''            lot = round(lot / step) * step
            lot = max(min_vol, min(lot, max_vol))
        else:
            dynamic_sl_points = atr * 1.5
            risk_money = equity * risk_pct
            lot = risk_money / max(dynamic_sl_points, 1.0)
            lot = max(0.01, round(lot, 2))
            
        # Phase 11: Risk Transparency & Lot Sizing Matrix
        logger.info(f"Risk Matrix -> Eq: \ | Risk%: {risk_pct*100:.2f}% (Max Loss: \) | ATR: {atr:.2f} | Conviction: {conviction:.2f} | Final Vol: {lot}")
            
        return lot'''

    content = content.replace(end_target, end_replace)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("? risk_manager.py patched successfully.")

if __name__ == '__main__':
    patch_risk_manager()
