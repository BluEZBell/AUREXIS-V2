import sqlite3
import pandas as pd
import numpy as np
import os
from typing import Tuple, Dict, Any

class DataDrivenAlphaTuner:
    def __init__(self, journal_path: str, db_path: str):
        self.journal_path = journal_path
        self.db_path = db_path

    def load_data(self) -> pd.DataFrame:
        if not os.path.exists(self.journal_path):
            df_journal = pd.DataFrame()
        else:
            df_journal = pd.read_csv(self.journal_path)

        if not os.path.exists(self.db_path):
            df_db = pd.DataFrame()
        else:
            conn = sqlite3.connect(self.db_path)
            try:
                df_db = pd.read_sql_query("SELECT * FROM cycles", conn)
            except Exception:
                df_db = pd.DataFrame()
            conn.close()

        if not df_journal.empty and not df_db.empty:
            # df_db has cycle_id, df_journal has Cycle_ID
            df_db = df_db.rename(columns={'cycle_id': 'Cycle_ID'})
            df = pd.merge(df_journal, df_db, on='Cycle_ID', how='inner')
        elif not df_journal.empty:
            df = df_journal
        else:
            df = pd.DataFrame()
            
        if df.empty:
            return df

        # Map logic correctly for Data-Driven Alpha Tuner
        # MFE is in df_db as 'mfe'
        if 'mfe' in df.columns:
            df['MFE'] = df['mfe']
        elif 'MFE' not in df.columns:
            df['MFE'] = 0.0

        # Execution level based on positions opened
        if 'Total_Positions_Opened' in df.columns:
            df['Execution_Level'] = np.where(df['Total_Positions_Opened'] > 1, 'SWARM', 'PROBE')
        else:
            df['Execution_Level'] = 'PROBE'

        # Nano Break-Even triggered if MFE > 0 and exited via SL spike
        if 'MFE' in df.columns and 'Exit_Reason' in df.columns:
            df['Nano_Break_Even_Triggered'] = (df['MFE'] > 0.0) & (df['Exit_Reason'] == 'HARD_SL_SPIKE')
        else:
            df['Nano_Break_Even_Triggered'] = False
            
        return df

    def analyze_mfe_capture(self, df: pd.DataFrame) -> Tuple[float, float]:
        if df.empty or 'Total_Realized_PnL' not in df.columns or 'MFE' not in df.columns:
            return 0.0, 0.0
            
        valid_df = df[df['MFE'] > 0].copy()
        if valid_df.empty:
            return 0.0, 0.0
            
        capture_rates = valid_df['Total_Realized_PnL'] / valid_df['MFE']
        return float(np.mean(capture_rates)), float(np.mean(valid_df['MFE']))

    def analyze_friction(self, df: pd.DataFrame) -> Tuple[int, float]:
        if df.empty or 'Nano_Break_Even_Triggered' not in df.columns or 'Total_Realized_PnL' not in df.columns:
            return 0, 0.0
            
        nbe_losses = df[(df['Nano_Break_Even_Triggered'] == True) & (df['Total_Realized_PnL'] < 0)]
        if nbe_losses.empty:
            return 0, 0.0
            
        return len(nbe_losses), float(np.mean(nbe_losses['Total_Realized_PnL']))

    def analyze_swarm_vs_probe(self, df: pd.DataFrame) -> Dict[str, Any]:
        result = {'swarm_win_rate': 0.0, 'probe_win_rate': 0.0, 'swarm_count': 0, 'probe_count': 0}
        if df.empty or 'Execution_Level' not in df.columns or 'Total_Realized_PnL' not in df.columns:
            return result
            
        swarm_df = df[df['Execution_Level'] == 'SWARM']
        probe_df = df[df['Execution_Level'] == 'PROBE']
        
        def calc_wr(sub_df):
            if sub_df.empty: return 0.0
            return float(len(sub_df[sub_df['Total_Realized_PnL'] > 0]) / len(sub_df))
            
        result['swarm_count'] = len(swarm_df)
        result['probe_count'] = len(probe_df)
        result['swarm_win_rate'] = calc_wr(swarm_df)
        result['probe_win_rate'] = calc_wr(probe_df)
        return result

    def run_analysis(self):
        df = self.load_data()
        
        mfe_capture_rate, avg_mfe = self.analyze_mfe_capture(df)
        nbe_fails, avg_slippage = self.analyze_friction(df)
        execution_stats = self.analyze_swarm_vs_probe(df)

        # 1. Suggested Nano Break-Even Friction Offset
        suggested_nbe_offset = max(1.0, abs(avg_slippage) * 1.5) if nbe_fails > 0 else 1.0

        # 2. Suggested Asymmetric Kelly Multiplier
        current_kelly = 3.0
        swarm_wr = execution_stats.get('swarm_win_rate', 0.0)
        if swarm_wr > 0.75:
            suggested_kelly = min(6.0, current_kelly + (swarm_wr - 0.75) * 10)
        else:
            suggested_kelly = current_kelly

        # 3. Suggested Tick Velocity Deceleration Threshold
        current_tick_threshold = 15.0
        if mfe_capture_rate < 0.5 and mfe_capture_rate > 0:
            suggested_tick_threshold = current_tick_threshold * 0.8
        elif mfe_capture_rate >= 0.7:
            suggested_tick_threshold = current_tick_threshold * 1.2
        else:
            suggested_tick_threshold = current_tick_threshold

        output_dict = {
            "Total_Cycles_Analyzed": len(df),
            "MFE_Capture_Rate": float(mfe_capture_rate),
            "NBE_Slippage_Fails": int(nbe_fails),
            "Avg_Slippage": float(avg_slippage),
            "SWARM_Win_Rate": float(swarm_wr),
            "SWARM_Count": int(execution_stats.get('swarm_count', 0)),
            "PROBE_Win_Rate": float(execution_stats.get('probe_win_rate', 0.0)),
            "PROBE_Count": int(execution_stats.get('probe_count', 0)),
            "Suggested_Nano_Break_Even_Friction_Offset": float(suggested_nbe_offset),
            "Suggested_Asymmetric_Kelly_Multiplier": float(suggested_kelly),
            "Suggested_Tick_Velocity_Decel_Threshold": float(suggested_tick_threshold)
        }
        
        try:
            import json
            os.makedirs('reports', exist_ok=True)
            with open('reports/alpha_tuner.json', 'w') as f:
                json.dump(output_dict, f, indent=4)
        except Exception as e:
            print(f"Failed to save JSON: {e}")

        print("="*60)
        print(" AUREXIS: DATA-DRIVEN ALPHA TUNER - EOD REPORT")
        print("="*60)
        print(f"Total Cycles Analyzed: {len(df)}")
        print(f"MFE Capture Rate:      {mfe_capture_rate:.2%}")
        print(f"NBE Slippage Fails:    {nbe_fails} (Avg Slippage: {avg_slippage:.2f})")
        print(f"SWARM Win Rate:        {swarm_wr:.2%} (Count: {execution_stats.get('swarm_count', 0)})")
        print(f"PROBE Win Rate:        {execution_stats.get('probe_win_rate', 0.0):.2%} (Count: {execution_stats.get('probe_count', 0)})")
        print("-" * 60)
        print(" ACTIONABLE OUTPUT MATRIX:")
        print("-" * 60)
        print(f"1. Suggested Nano Break-Even Friction Offset: +{suggested_nbe_offset:.2f} points")
        print(f"2. Suggested Asymmetric Kelly Multiplier:     {suggested_kelly:.2f}x")
        print(f"3. Suggested Tick Velocity Decel Threshold:   {suggested_tick_threshold:.2f}")
        print("="*60)

if __name__ == "__main__":
    tuner = DataDrivenAlphaTuner(
        journal_path="logs/institutional_journal.csv",
        db_path="campaign_ledger.db"
    )
    tuner.run_analysis()
