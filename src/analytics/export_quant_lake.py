import sqlite3
import csv
import os
import time
from datetime import datetime

def main():
    # Resolve db path relative to this script or current working directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    db_path = os.path.join(project_root, "db", "aurexis_quant_lake.db")
    
    if not os.path.exists(db_path):
        # Fallback if run directly from a different root
        db_path = "db/aurexis_quant_lake.db"
        if not os.path.exists(db_path):
            print(f"❌ Database not found at {db_path}. No data to export.")
            print("   Make sure AUREXIS is running and has generated snapshots.")
            return

    print("=== AUREXIS Quant Ops Exporter & Validator ===")
    print("Connecting to Data Lake (Read-Only Mode)...")
    
    # Use URI for read-only connection to avoid WAL locks
    # Windows paths need to be formatted correctly for sqlite URI
    db_uri_path = db_path.replace('\\', '/')
    uri = f"file:{db_uri_path}?mode=ro"
    
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError as e:
        print(f"❌ Failed to connect to database: {e}")
        return

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM feature_snapshots")
        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"❌ Failed to query feature_snapshots: {e}")
        conn.close()
        return

    total_records = len(rows)
    if total_records == 0:
        print("⚠️ Data Lake is empty. No snapshots recorded yet.")
        conn.close()
        return

    fully_labeled = 0
    orphans = 0
    anomalies = 0
    clean_data = []
    
    current_time = time.time()
    
    for row in rows:
        row_dict = dict(row)
        
        # Integrity Checks
        result_pnl = row_dict.get("result_pnl")
        timestamp = row_dict.get("timestamp", current_time)
        age_hours = (current_time - timestamp) / 3600.0
        
        is_orphan = False
        # Note: If result_pnl is strictly 0.0 and older than 24h, it's flagged as an orphan
        # (Assuming 0.0 is the initial unsettled state or NULL if schema allows)
        if result_pnl is None or (result_pnl == 0.0 and age_hours > 24):
            is_orphan = True
            orphans += 1
            
        is_anomaly = False
        slippage = row_dict.get("slippage_points", 0.0)
        dxy = row_dict.get("dxy_val", 0.0)
        us10y = row_dict.get("us10y_val", 0.0)
        
        # Check for Slippage Spikes or Feed Disconnections
        if slippage > 500 or dxy == 0.0 or us10y == 0.0:
            is_anomaly = True
            anomalies += 1
            
        if not is_orphan:
            fully_labeled += 1
            # We filter out anomalies from the clean ML dataset to prevent garbage training data
            if not is_anomaly:
                clean_data.append(row_dict)

    print("\n📊 --- DATA INTEGRITY REPORT ---")
    print(f"Total Records Captured : {total_records}")
    print(f"Fully Labeled (Usable) : {fully_labeled}")
    print(f"Orphaned (Missing PnL) : {orphans} (>24h without CLOSED_SYNC)")
    print(f"Anomalies Detected     : {anomalies} (Spike slippage > 500 or missing Macro feeds)")
    print("--------------------------------\n")

    if not clean_data:
        print("⚠️ No clean, labeled data available for export yet.")
        conn.close()
        return

    # Export Mechanism
    export_dir = os.path.join(project_root, "analytics_export")
    if not os.path.exists(export_dir):
        # Fallback to local if project root isn't right
        export_dir = "analytics_export"
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)
        
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_file = os.path.join(export_dir, f"dataset_{timestamp_str}.csv")
    
    fieldnames = clean_data[0].keys()
    
    try:
        with open(export_file, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(clean_data)
        
        print(f"✅ SUCCESS: Clean dataset exported to: {export_file}")
        print("💡 INSTRUCTION: You can now load this CSV into your Jupyter Notebook.")
        print("   Example: `import pandas as pd; df = pd.read_csv('dataset_...csv')`")
        print("   Target Variable (Y) = 'result_pnl'")
        print("   Features (X) = 'conviction_score', 'dxy_val', 'us10y_val', 'm15_atr', 'spread_points', 'slippage_points'")
    except Exception as e:
        print(f"❌ Failed to write CSV export: {e}")

    conn.close()

if __name__ == "__main__":
    main()
