import os
import argparse
import logging
import pandas as pd
import numpy as np
from typing import Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("JournalAnalyzer")

def load_journal(filepath: str) -> pd.DataFrame:
    """
    Load trade_journal.csv into a pandas DataFrame.
    Handles potential missing values, partial writes, or empty files gracefully.
    """
    if not os.path.exists(filepath):
        logger.warning(f"File not found: {filepath}")
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(filepath)
        # Handle empty file
        if df.empty:
            logger.warning(f"File is empty: {filepath}")
            return pd.DataFrame()
            
        # Ensure we have the minimum required columns for basic calculations
        if 'Final PnL' not in df.columns or 'Direction' not in df.columns:
            logger.warning("Missing critical columns (Final PnL, Direction) in the journal.")
            return pd.DataFrame()
            
        # Convert necessary columns to numeric FIRST so invalid strings become NaN
        numeric_cols = [
            'Entry Price', 'Exit Price', 'Conviction Score', 'Slippage',
            'Tick-to-Trade Latency', 'Total Holding Time', 'Final PnL', 'MFE', 'MAE'
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Then drop rows that are missing critical data due to partial writes
        df.dropna(subset=['Final PnL', 'Direction'], inplace=True)
        
        return df
    except pd.errors.EmptyDataError:
        logger.warning(f"File is empty (EmptyDataError): {filepath}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error loading {filepath}: {e}")
        return pd.DataFrame()

def calculate_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculates Quantitative Metrics.
    """
    if df.empty:
        return {}
    
    total_trades: int = len(df)
    
    # Win / Loss split
    winners = df[df['Final PnL'] > 0]
    losers = df[df['Final PnL'] <= 0]
    
    win_rate: float = (len(winners) / total_trades * 100) if total_trades > 0 else 0.0
    total_pnl: float = float(df['Final PnL'].sum())
    
    gross_profit: float = float(winners['Final PnL'].sum())
    gross_loss: float = float(abs(losers['Final PnL'].sum()))
    
    profit_factor: float = (gross_profit / gross_loss) if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0)
    expectancy: float = total_pnl / total_trades if total_trades > 0 else 0.0
    
    # Precision Metrics
    avg_mfe: float = float(df['MFE'].mean()) if 'MFE' in df.columns else 0.0
    if pd.isna(avg_mfe): avg_mfe = 0.0
        
    avg_mae: float = float(df['MAE'].mean()) if 'MAE' in df.columns else 0.0
    if pd.isna(avg_mae): avg_mae = 0.0
        
    mfe_mae_ratio: float = (avg_mfe / avg_mae) if avg_mae > 0 else (float('inf') if avg_mfe > 0 else 0.0)
    
    # Operational Metrics
    avg_holding_time_winners: float = float(winners['Total Holding Time'].mean()) if 'Total Holding Time' in df.columns else 0.0
    if pd.isna(avg_holding_time_winners): avg_holding_time_winners = 0.0
        
    avg_holding_time_losers: float = float(losers['Total Holding Time'].mean()) if 'Total Holding Time' in df.columns else 0.0
    if pd.isna(avg_holding_time_losers): avg_holding_time_losers = 0.0
        
    avg_latency: float = float(df['Tick-to-Trade Latency'].mean()) if 'Tick-to-Trade Latency' in df.columns else 0.0
    if pd.isna(avg_latency): avg_latency = 0.0
    
    return {
        "Total Trades": total_trades,
        "Win Rate (%)": win_rate,
        "Total PnL": total_pnl,
        "Profit Factor": profit_factor,
        "Mathematical Expectancy": expectancy,
        "Average MFE (Points)": avg_mfe,
        "Average MAE (Points)": avg_mae,
        "MFE/MAE Ratio": mfe_mae_ratio,
        "Avg Holding Time Winners (s)": avg_holding_time_winners,
        "Avg Holding Time Losers (s)": avg_holding_time_losers,
        "Avg Tick-to-Trade Latency (ms)": avg_latency
    }

def print_report(metrics: Dict[str, Any]) -> None:
    """
    Output a clearly formatted, console-based statistical report.
    """
    if not metrics:
        logger.info("No data available to generate a report.")
        return
        
    report = f"""
=========================================================
          QUANTITATIVE ANALYTICS ENGINE REPORT           
=========================================================
CORE PERFORMANCE METRICS
---------------------------------------------------------
Total Trades               : {metrics['Total Trades']}
Win Rate                   : {metrics['Win Rate (%)']:.2f}%
Total PnL                  : {metrics['Total PnL']:.2f}
Profit Factor              : {metrics['Profit Factor']:.2f}
Mathematical Expectancy    : {metrics['Mathematical Expectancy']:.2f} per trade

PRECISION METRICS (Alpha Proof)
---------------------------------------------------------
Average MFE                : {metrics['Average MFE (Points)']:.2f} Points
Average MAE                : {metrics['Average MAE (Points)']:.2f} Points
MFE/MAE Ratio              : {metrics['MFE/MAE Ratio']:.2f}

OPERATIONAL METRICS
---------------------------------------------------------
Avg Holding Time (Winners) : {metrics['Avg Holding Time Winners (s)']:.2f} seconds
Avg Holding Time (Losers)  : {metrics['Avg Holding Time Losers (s)']:.2f} seconds
Avg Tick-to-Trade Latency  : {metrics['Avg Tick-to-Trade Latency (ms)']:.2f} ms
=========================================================
"""
    logger.info(report)

def main() -> None:
    parser = argparse.ArgumentParser(description="Quantitative Analytics Engine for Trade Journal")
    parser.add_argument("--journal", type=str, default="trade_journal.csv", help="Path to trade_journal.csv")
    args = parser.parse_args()
    
    df = load_journal(args.journal)
    metrics = calculate_metrics(df)
    print_report(metrics)

if __name__ == "__main__":
    main()
