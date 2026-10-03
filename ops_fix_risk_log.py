import os

def patch_risk_manager():
    file_path = 'src/execution/risk_manager.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Re-replace the broken line
    broken_log = '        logger.info(f"Risk Matrix -> Eq: \ | Risk%: {risk_pct*100:.2f}% (Max Loss: \) | ATR: {atr:.2f} | Conviction: {conviction:.2f} | Final Vol: {lot}")'
    correct_log = '        logger.info(f"Risk Matrix -> Eq: ${equity:.2f} | Risk%: {risk_pct*100:.2f}% (Max Loss: ${equity*risk_pct:.2f}) | ATR: {atr:.2f} | Conviction: {conviction:.2f} | Final Vol: {lot}")'
    
    content = content.replace(broken_log, correct_log)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("? risk_manager.py log line fixed.")

if __name__ == '__main__':
    patch_risk_manager()
