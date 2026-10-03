import os
import sqlite3
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("train_oracle")

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))

DB_PATH = os.path.join(project_root, "db", "aurexis_quant_lake.db")
MODEL_DIR = os.path.join(project_root, "models")
MODEL_PATH = os.path.join(MODEL_DIR, "aurexis_oracle.pkl")

def main():
    logger.info("Initializing The Alchemist (Model Training Pipeline)...")
    
    if not os.path.exists(DB_PATH):
        logger.error(f"Data Lake not found at {DB_PATH}. Exiting.")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        query = '''
            SELECT 
                conviction_score, dxy_val, us10y_val, m15_atr, spread_points, result_pnl
            FROM feature_snapshots
            WHERE result_pnl IS NOT NULL
        '''
        df = pd.read_sql(query, conn)
        conn.close()
    except Exception as e:
        logger.error(f"Failed to extract data: {e}")
        return

    if df.empty or len(df) < 50:
        logger.warning(f"Insufficient data for training. Found {len(df)} rows, minimum required is 50.")
        # But we will mock the dataset just for testing if it's empty, or we can just exit.
        # Wait, the prompt says: "If the database does not exist or has too few rows (e.g., < 50 trades), log an error and exit gracefully without crashing."
        logger.error("Exiting gracefully.")
        return

    df = df.dropna()
    if len(df) < 50:
        logger.error("Insufficient data after dropping NaNs. Exiting gracefully.")
        return

    df['y'] = (df['result_pnl'] > 0).astype(int)
    
    features = ['conviction_score', 'dxy_val', 'us10y_val', 'm15_atr', 'spread_points']
    X = df[features]
    y = df['y']
    
    wins = (y == 1).sum()
    losses = (y == 0).sum()
    
    logger.info(f"Dataset Size: {len(df)} rows")
    logger.info(f"Class Distribution -> Wins: {wins}, Losses: {losses}")
    
    logger.info("Training RandomForestClassifier...")
    model = RandomForestClassifier(n_estimators=100, max_depth=5, min_samples_leaf=10, random_state=42)
    model.fit(X, y)
    
    accuracy = model.score(X, y)
    logger.info(f"Training Accuracy: {accuracy * 100:.2f}%")
    
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    logger.info(f"Model successfully exported to {MODEL_PATH}")

if __name__ == "__main__":
    main()
