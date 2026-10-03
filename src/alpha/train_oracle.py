import os
import sqlite3
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
import logging

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("train_oracle")

    # Resolve DB path safely
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    db_path = os.path.join(project_root, "db", "aurexis_quant_lake.db")
    
    if not os.path.exists(db_path):
        db_path = "db/aurexis_quant_lake.db"
        if not os.path.exists(db_path):
            logger.error(f"Database not found at {db_path}")
            return
            
    conn = sqlite3.connect(db_path)
    query = "SELECT * FROM feature_snapshots WHERE result_pnl IS NOT NULL"
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        logger.warning("No labeled data found for training.")
        return

    # Drop nulls and sanitize
    df = df.dropna(subset=['conviction_score', 'dxy_val', 'us10y_val', 'm15_atr', 'spread_points', 'result_pnl'])
    
    # Filter anomalies (like in export script)
    # df = df[(df['dxy_val'] != 0.0) & (df['us10y_val'] != 0.0)]
    
    if df.empty:
        logger.warning("No clean labeled data found for training after anomaly filtering.")
        return

    # Create Binary Target
    df['target'] = (df['result_pnl'] > 0).astype(int)
    
    features = ['conviction_score', 'dxy_val', 'us10y_val', 'm15_atr', 'spread_points']
    X = df[features]
    y = df['target']
    
    if len(df) < 50:
        logger.warning("Very small dataset, model might overfit or fail. Proceeding anyway for pipeline demonstration.")
        
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    clf.fit(X_train, y_train)
    
    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    logger.info(f"Model Training Complete. Validation Accuracy: {acc:.2f}")
    logger.info(f"Classification Report:\n{classification_report(y_test, y_pred, zero_division=0)}")
    
    # Save the model
    os.makedirs(os.path.join(project_root, "models"), exist_ok=True)
    model_path = os.path.join(project_root, "models", "aurexis_oracle.pkl")
    joblib.dump(clf, model_path)
    logger.info(f"Trained MLOracle model saved to {model_path}")

if __name__ == "__main__":
    main()
