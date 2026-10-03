import asyncio
import os
import sys
import logging
from typing import Dict, Any, Tuple
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("quant_analyzer")

class JournalReader:
    """Handles async loading and parsing of journal CSVs."""
    def __init__(self, journal_path: str, trade_journal_path: str):
        self.journal_path = journal_path
        self.trade_journal_path = trade_journal_path

    async def load_journal(self) -> pd.DataFrame:
        def _read_csv() -> pd.DataFrame:
            if not os.path.exists(self.journal_path):
                logger.error(f"Journal not found at {self.journal_path}")
                raise FileNotFoundError
            try:
                df = pd.read_csv(self.journal_path)
                if df.empty:
                    return df
                
                df['Total_Positions_Opened'] = pd.to_numeric(df['Total_Positions_Opened'], errors='coerce').fillna(0).astype(int)
                df['Max_Conviction_Score'] = pd.to_numeric(df['Max_Conviction_Score'], errors='coerce').fillna(0.0)
                df['Total_Realized_PnL'] = pd.to_numeric(df['Total_Realized_PnL'], errors='coerce').fillna(0.0)
                return df
            except Exception as e:
                logger.error(f"Failed to read or parse the journal CSV: {e}")
                raise

        return await asyncio.to_thread(_read_csv)

    async def load_trade_journal(self) -> pd.DataFrame:
        def _read_csv() -> pd.DataFrame:
            if not os.path.exists(self.trade_journal_path):
                return pd.DataFrame()
            try:
                headers = ['Order Ticket','Direction','Entry Price','Exit Price','Conviction Score','Slippage','Tick-to-Trade Latency','Total Holding Time','Final PnL','MFE','MAE']
                df = pd.read_csv(self.trade_journal_path, names=headers)
                if df.empty:
                    return df
                
                df['MFE'] = pd.to_numeric(df['MFE'], errors='coerce').fillna(0.0)
                df['MAE'] = pd.to_numeric(df['MAE'], errors='coerce').fillna(0.0)
                df['Final PnL'] = pd.to_numeric(df['Final PnL'], errors='coerce').fillna(0.0)
                return df
            except Exception as e:
                logger.warning(f"Failed to read trade journal CSV: {e}")
                return pd.DataFrame()

        return await asyncio.to_thread(_read_csv)


class MetricCalculator:
    """Handles all vectorized calculations using pandas."""
    def __init__(self, df: pd.DataFrame, trade_df: pd.DataFrame):
        self.df = df
        self.trade_df = trade_df

    def calculate_core_metrics(self) -> Dict[str, Any]:
        """Calculates overarching performance metrics."""
        if self.df.empty:
            return {}
            
        total_trades = len(self.df)
        wins = self.df[self.df['Total_Realized_PnL'] > 0]
        losses = self.df[self.df['Total_Realized_PnL'] <= 0]
        
        win_rate = len(wins) / total_trades if total_trades > 0 else 0.0
        
        gross_profit = wins['Total_Realized_PnL'].sum()
        gross_loss = abs(losses['Total_Realized_PnL'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        avg_win = wins['Total_Realized_PnL'].mean() if not wins.empty else 0.0
        avg_loss = losses['Total_Realized_PnL'].mean() if not losses.empty else 0.0
        
        cumulative_pnl = self.df['Total_Realized_PnL'].cumsum()
        peak = cumulative_pnl.cummax()
        drawdown = peak - cumulative_pnl
        max_drawdown = drawdown.max() if not drawdown.empty else 0.0

        return {
            "Total_Campaigns": total_trades,
            "Absolute_Win_Rate": win_rate,
            "Profit_Factor": profit_factor,
            "Average_Win": avg_win,
            "Average_Loss": avg_loss,
            "Max_Drawdown": max_drawdown,
            "Net_PnL": cumulative_pnl.iloc[-1] if not cumulative_pnl.empty else 0.0
        }

    def evaluate_pyramiding_efficiency(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if self.df.empty:
            return {}, {}
        single_probe = self.df[self.df['Total_Positions_Opened'] == 1]
        multi_probe = self.df[self.df['Total_Positions_Opened'] > 1]
        
        def calc_sub_metrics(sub_df: pd.DataFrame) -> Dict[str, Any]:
            if sub_df.empty:
                return {"Count": 0, "Win_Rate": 0.0, "Net_PnL": 0.0}
            wins = sub_df[sub_df['Total_Realized_PnL'] > 0]
            win_rate = len(wins) / len(sub_df)
            net_pnl = sub_df['Total_Realized_PnL'].sum()
            return {"Count": len(sub_df), "Win_Rate": win_rate, "Net_PnL": net_pnl}

        return calc_sub_metrics(single_probe), calc_sub_metrics(multi_probe)

    def evaluate_oracle_accuracy(self) -> Dict[str, Any]:
        if self.df.empty:
            return {}
        
        high_conv = self.df[self.df['Max_Conviction_Score'] > 80.0]
        normal_conv = self.df[self.df['Max_Conviction_Score'] <= 80.0]
        
        def calc_sub(sub_df: pd.DataFrame):
            if sub_df.empty: return {"Count": 0, "Win_Rate": 0.0, "Net_PnL": 0.0}
            wr = len(sub_df[sub_df['Total_Realized_PnL'] > 0]) / len(sub_df)
            return {"Count": len(sub_df), "Win_Rate": wr, "Net_PnL": sub_df['Total_Realized_PnL'].sum()}
            
        return {
            "High_Conviction (>80)": calc_sub(high_conv),
            "Normal_Conviction (<=80)": calc_sub(normal_conv)
        }

    def evaluate_regime_edge(self) -> pd.DataFrame:
        if self.df.empty:
            return pd.DataFrame()
            
        def regime_metrics(group):
            wins = group[group['Total_Realized_PnL'] > 0]
            losses = group[group['Total_Realized_PnL'] <= 0]
            gross_profit = wins['Total_Realized_PnL'].sum()
            gross_loss = abs(losses['Total_Realized_PnL'].sum())
            pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            wr = len(wins) / len(group) if len(group) > 0 else 0.0
            return pd.Series({
                'Count': len(group),
                'Win_Rate': wr,
                'Profit_Factor': pf,
                'Net_PnL': group['Total_Realized_PnL'].sum()
            })
            
        return self.df.groupby('Regime_At_Entry').apply(regime_metrics)
        
    def evaluate_execution_friction(self) -> Dict[str, Any]:
        if self.trade_df.empty:
            return {}
        
        wins = self.trade_df[self.trade_df['Final PnL'] > 0]
        losses = self.trade_df[self.trade_df['Final PnL'] <= 0]
        
        return {
            "Avg_MFE_Wins": wins['MFE'].mean() if not wins.empty else 0.0,
            "Avg_MAE_Wins": wins['MAE'].mean() if not wins.empty else 0.0,
            "Avg_MFE_Losses": losses['MFE'].mean() if not losses.empty else 0.0,
            "Avg_MAE_Losses": losses['MAE'].mean() if not losses.empty else 0.0,
            "Max_MFE_All": self.trade_df['MFE'].max(),
            "Max_MAE_All": self.trade_df['MAE'].min()  # MAE is typically negative or tracked as absolute depending on implementation. Let's use min if it's negative points.
        }


class ReportGenerator:
    """Formats and outputs the professional terminal report."""
    
    @staticmethod
    def generate(
        core: Dict[str, Any], 
        single: Dict[str, Any], 
        multi: Dict[str, Any], 
        oracle: Dict[str, Any], 
        regime: pd.DataFrame,
        friction: Dict[str, Any]
    ):
        print("="*75)
        print("         AUREXIS V2 - INSTITUTIONAL QUANTITATIVE JOURNAL ANALYZER         ")
        print("="*75)
        if not core:
            print("NO TRADING DATA AVAILABLE TO ANALYZE.")
            print("="*75)
            return
            
        print("\n[1] CORE METRICS")
        print(f"  Total Campaigns   : {core.get('Total_Campaigns', 0)}")
        print(f"  Net PnL           : ${core.get('Net_PnL', 0.0):.2f}")
        print(f"  Absolute Win Rate : {core.get('Absolute_Win_Rate', 0.0)*100:.2f}%")
        print(f"  Profit Factor     : {core.get('Profit_Factor', 0.0):.2f}")
        print(f"  Average Win       : ${core.get('Average_Win', 0.0):.2f}")
        print(f"  Average Loss      : ${core.get('Average_Loss', 0.0):.2f}")
        print(f"  Max Drawdown      : ${core.get('Max_Drawdown', 0.0):.2f}")

        print("\n[2] FREE-ROLL PYRAMIDING EFFICIENCY")
        print("  Single-Probe (1 Position):")
        print(f"    Count: {single.get('Count', 0):>3} | Win Rate: {single.get('Win_Rate', 0.0)*100:>5.2f}% | PnL: ${single.get('Net_PnL', 0.0):.2f}")
        print("  Multi-Probe (>1 Position - Free-Roll):")
        print(f"    Count: {multi.get('Count', 0):>3} | Win Rate: {multi.get('Win_Rate', 0.0)*100:>5.2f}% | PnL: ${multi.get('Net_PnL', 0.0):.2f}")

        print("\n[3] ML ORACLE PREDICTIVE EDGE")
        for k, v in oracle.items():
            print(f"  {k:25}:")
            print(f"    Count: {v.get('Count', 0):>3} | Win Rate: {v.get('Win_Rate', 0.0)*100:>5.2f}% | PnL: ${v.get('Net_PnL', 0.0):.2f}")

        print("\n[4] REGIME EDGE (PROFIT FACTOR BY REGIME)")
        if not regime.empty:
            for index, row in regime.iterrows():
                print(f"  {index:10}:")
                print(f"    Count: {int(row['Count']):>3} | Win Rate: {row['Win_Rate']*100:>5.2f}% | PF: {row['Profit_Factor']:>6.2f} | PnL: ${row['Net_PnL']:.2f}")
        else:
            print("  No regime data.")
            
        print("\n[5] EXECUTION FRICTION & MFE/MAE DISTRIBUTIONS")
        if friction:
            print(f"  Avg MFE (Winning Trades) : {friction.get('Avg_MFE_Wins', 0.0):.1f} pts")
            print(f"  Avg MAE (Winning Trades) : {friction.get('Avg_MAE_Wins', 0.0):.1f} pts")
            print(f"  Avg MFE (Losing Trades)  : {friction.get('Avg_MFE_Losses', 0.0):.1f} pts")
            print(f"  Avg MAE (Losing Trades)  : {friction.get('Avg_MAE_Losses', 0.0):.1f} pts")
            print(f"  Max MFE (Best Excursion) : {friction.get('Max_MFE_All', 0.0):.1f} pts")
            print(f"  Max MAE (Worst Excursion): {friction.get('Max_MAE_All', 0.0):.1f} pts")
        else:
            print("  No trade journal MFE/MAE data available.")
            
        print("="*75)
        print("                END OF REPORT - AWAITING FUND MANAGER DIRECTIVES          ")
        print("="*75)


async def main():
    journal_path = os.path.join("logs", "institutional_journal.csv")
    trade_journal_path = "trade_journal.csv"
    reader = JournalReader(journal_path, trade_journal_path)
    
    try:
        df = await reader.load_journal()
        trade_df = await reader.load_trade_journal()
    except Exception:
        sys.exit(1)
        
    calc = MetricCalculator(df, trade_df)
    core_metrics = calc.calculate_core_metrics()
    single, multi = calc.evaluate_pyramiding_efficiency()
    oracle_metrics = calc.evaluate_oracle_accuracy()
    regime_metrics = calc.evaluate_regime_edge()
    friction = calc.evaluate_execution_friction()
    
    ReportGenerator.generate(core_metrics, single, multi, oracle_metrics, regime_metrics, friction)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
