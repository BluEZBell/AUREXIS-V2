import sqlite3
import pandas as pd
import os

try:
    if os.path.exists("campaign_ledger.db"):
        conn = sqlite3.connect("campaign_ledger.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("Tables:", tables)
        for t in tables:
            df = pd.read_sql_query(f"SELECT * FROM {t[0]} LIMIT 5", conn)
            print(f"Table {t[0]} columns:", df.columns.tolist())
except Exception as e:
    print(e)
try:
    if os.path.exists("logs/institutional_journal.csv"):
        df = pd.read_csv("logs/institutional_journal.csv", nrows=5)
        print("CSV columns:", df.columns.tolist())
except Exception as e:
    print(e)
