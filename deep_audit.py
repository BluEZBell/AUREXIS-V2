import os
import re
import sys

# enforce utf8 for printing
sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = r"c:\Users\bluzp\AUREXISV2"

def parse_logs(filepath, keywords, lines_before=0, lines_after=0, max_results=50):
    full_path = os.path.join(BASE_DIR, filepath)
    if not os.path.exists(full_path):
        print(f"File not found: {full_path}")
        return
    
    with open(full_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    results = []
    for i, line in enumerate(lines):
        if any(k.lower() in line.lower() for k in keywords):
            start = max(0, i - lines_before)
            end = min(len(lines), i + lines_after + 1)
            results.append("".join(lines[start:end]).strip())
    
    # Print only the latest occurrences
    for r in results[-max_results:]:
        print(r)

print("=== LAYER 1: COGNITIVE (Bayesian Score Matrix & Signals) ===")
parse_logs("logs/alpha_harvester.log", ["Conviction", "Score: 90", "STRUCTURAL SHIFT"], 0, 0, 30)

print("\n=== LAYER 2: SENTINEL (หนีตาย & บังทุน) ===")
parse_logs("logs/alpha_harvester.log", ["Adaptive Correction", "Momentum", "SCRATCH"], 0, 0, 30)
parse_logs("logs/tick_sentinel.log", ["Tier", "Break-Even", "API Spam"], 0, 0, 30)

print("\n=== LAYER 3: EXECUTION (การเข้าไม้และบล็อก) ===")
parse_logs("logs/execution_bridge.log", ["DOOMSDAY", "SHIELD", "Error", "Reject", "Margin", "FILLED"], 0, 0, 30)

