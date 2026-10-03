import os
import re

def fix_ml_oracle():
    file_path = 'src/analytics/ml_oracle.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = """            # Extract standard indicator features
            features = [
                float(current_features.get('curr_price', 0.0)),
                float(current_features.get('ema20_m15', 0.0)),
                float(current_features.get('ema50_m15', 0.0)),
                float(current_features.get('rsi', 50.0)),
                float(current_features.get('adx_m15', 0.0)),
                float(current_features.get('atr_m15', 0.0)),
                float(current_features.get('bb_upper', 0.0)),
                float(current_features.get('bb_lower', 0.0)),
                float(current_features.get('adx_m15_rising', 0.0)),
                float(current_features.get('ema_expansion', 0.0))
            ]"""
    
    replace = """            # Extract standard indicator features
            features = [
                float(current_features.get('conviction_score', 0.0)),
                float(current_features.get('dxy_val', 0.0)),
                float(current_features.get('us10y_val', 0.0)),
                float(current_features.get('m15_atr', 0.0)),
                float(current_features.get('spread_points', 0.0))
            ]"""
            
    content = content.replace(target, replace)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("? Fixed MLOracle feature extraction")

if __name__ == '__main__':
    fix_ml_oracle()
