import os
import sqlite3
import pandas as pd
import numpy as np
import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
import joblib
import asyncio
from src.core.event_bus import CommandEvent

console = Console()

class TearsheetGenerator:
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.ledger_db = os.path.join(self.project_root, "db", "aurexis_ledger.db")
        self.lake_db = os.path.join(self.project_root, "db", "aurexis_quant_lake.db")
        self.model_path = os.path.join(self.project_root, "models", "aurexis_oracle.pkl")
        self.reports_dir = os.path.join(self.project_root, "reports")
        os.makedirs(self.reports_dir, exist_ok=True)

    async def generate(self):
        console.print("[bold cyan]Initiating Phase 10: Portfolio Analytics & ML Drift Monitor...[/]")
        
        # 1. Trading Metrics from Campaign Ledger
        metrics = self._calculate_trading_metrics()
        
        # 2. ML Drift Monitoring from Quant Lake
        ml_metrics = self._calculate_ml_drift()
        
        # 3. Generate Report
        await self._generate_report(metrics, ml_metrics)

    def _calculate_shield_blocks(self) -> int:
        logs_dir = os.path.join(self.project_root, "logs")
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        blocked = 0
        
        target_logs = ["execution_bridge.log", "risk_manager.log"]
        import glob
        
        for base_log in target_logs:
            log_files = glob.glob(os.path.join(logs_dir, base_log + "*"))
            for log_file in log_files:
                if not os.path.exists(log_file):
                    continue
                try:
                    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            if line.startswith(date_str):
                                lower_line = line.lower()
                                if "rejected" in lower_line or "blocked" in lower_line or "shield block" in lower_line:
                                    blocked += 1
                except Exception:
                    pass
        return blocked

    def _calculate_trading_metrics(self) -> dict:
        if not os.path.exists(self.ledger_db):
            return {"error": f"Ledger DB not found at {self.ledger_db}", "shield_blocks": self._calculate_shield_blocks()}
            
        try:
            uri = f"file:{self.ledger_db}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
            df = pd.read_sql_query("SELECT cycle_id, direction, realized_pnl FROM cycles WHERE state = 'CLOSED'", conn)
            conn.close()
        except Exception as e:
            return {"error": str(e), "shield_blocks": self._calculate_shield_blocks()}

        if df.empty:
            return {"error": "No CLOSED cycles found for analysis.", "shield_blocks": self._calculate_shield_blocks()}

        total_pnl = df['realized_pnl'].sum()
        
        winning_trades = df[df['realized_pnl'] > 0]
        losing_trades = df[df['realized_pnl'] <= 0]
        
        total_trades = len(df)
        win_rate = (len(winning_trades) / total_trades) * 100.0 if total_trades > 0 else 0.0
        
        gross_profit = winning_trades['realized_pnl'].sum()
        gross_loss = abs(losing_trades['realized_pnl'].sum())
        
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')
        
        avg_win = winning_trades['realized_pnl'].mean() if not winning_trades.empty else 0.0
        avg_loss = abs(losing_trades['realized_pnl'].mean()) if not losing_trades.empty else 0.0
        
        avg_rr = (avg_win / avg_loss) if avg_loss > 0 else float('inf')
        
        cumulative = df['realized_pnl'].cumsum()
        peak = cumulative.cummax()
        drawdown = peak - cumulative
        max_drawdown = drawdown.max()
        
        return {
            "total_trades": total_trades,
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_rr": avg_rr,
            "max_drawdown": max_drawdown,
            "shield_blocks": self._calculate_shield_blocks()
        }

    def _calculate_ml_drift(self) -> dict:
        if not os.path.exists(self.lake_db):
            return {"error": "Quant Lake DB not found."}
            
        if not os.path.exists(self.model_path):
            return {"error": "ML Model (aurexis_oracle.pkl) not found. Cannot evaluate drift."}
            
        try:
            uri = f"file:{self.lake_db}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
            df = pd.read_sql_query("SELECT * FROM feature_snapshots WHERE result_pnl IS NOT NULL", conn)
            conn.close()
        except Exception as e:
            return {"error": str(e)}

        if df.empty:
            return {"error": "No completed snapshots found in Quant Lake."}

        if 'ml_prob' not in df.columns:
            features = ['conviction_score', 'dxy_val', 'us10y_val', 'm15_atr', 'spread_points']
            df = df.dropna(subset=features)
            if df.empty:
                return {"error": "No complete feature snapshots found for ML inference."}
                
            try:
                model = joblib.load(self.model_path)
                X = df[features]
                probs = model.predict_proba(X)
                df['ml_prob'] = probs[:, 1]
            except Exception as e:
                return {"error": f"Model inference failed: {str(e)}"}

        high_prob_trades = df[df['ml_prob'] >= 0.60]
        total_high_prob = len(high_prob_trades)
        
        if total_high_prob == 0:
            return {
                "total_eval": 0,
                "realized_accuracy": 0.0,
                "drift_warning": False,
                "message": "No trades evaluated with Probability >= 0.60"
            }
            
        winning_high_prob = high_prob_trades[high_prob_trades['result_pnl'] > 0]
        realized_accuracy = (len(winning_high_prob) / total_high_prob) * 100.0
        
        drift_warning = realized_accuracy < 50.0
        
        return {
            "total_eval": total_high_prob,
            "realized_accuracy": realized_accuracy,
            "drift_warning": drift_warning
        }

    async def _generate_report(self, metrics: dict, ml_metrics: dict):
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        report_path = os.path.join(self.reports_dir, f"tearsheet_{date_str}.md")
        json_path = os.path.join(self.reports_dir, f"tearsheet_{date_str}.json")
        
        lines = []
        lines.append(f"# AUREXIS Tear Sheet ({date_str})")
        lines.append("## Portfolio Analytics")
        if "error" in metrics:
            lines.append(f"**Error:** {metrics['error']}")
        else:
            lines.append(f"- **Total Campaigns (Closed):** {metrics['total_trades']}")
            lines.append(f"- **Total PnL:** ")
            lines.append(f"- **Win Rate:** {metrics['win_rate']:.2f}%")
            lines.append(f"- **Profit Factor:** {metrics['profit_factor']:.2f}")
            lines.append(f"- **Average Risk/Reward:** {metrics['avg_rr']:.2f}")
            lines.append(f"- **Maximum Drawdown (Closed Equity):** ")

        lines.append("\n## ML Drift Monitor")
        if "error" in ml_metrics:
            lines.append(f"**Error:** {ml_metrics['error']}")
        elif ml_metrics.get("total_eval", 0) == 0:
            lines.append(ml_metrics.get("message", "No high-probability trades found."))
        else:
            acc = ml_metrics['realized_accuracy']
            lines.append(f"- **High-Probability Trades Evaluated:** {ml_metrics['total_eval']}")
            lines.append(f"- **Realized Accuracy (Prob >= 0.60):** {acc:.2f}%")
            
            if ml_metrics['drift_warning']:
                lines.append("\n> **🚨 MODEL DRIFT WARNING:** Realized accuracy has dropped below 50%. The model is losing its predictive edge due to concept drift. Immediate RETRAIN_ORACLE is required.")
                if self.event_bus:
                    console.print("[bold red blink]Model Drift Detected. Dispatching RETRAIN_ORACLE command to Orchestrator...[/]")
                    await self.event_bus.publish(CommandEvent(action="RETRAIN_ORACLE"))
            else:
                lines.append("\n> **✅ ORACLE HEALTHY:** Model accuracy is maintaining its edge over the market.")

        md_content = "\n".join(lines)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        import json
        shield_blocks = metrics.get('shield_blocks', 0)
        json_payload = {
            "Total Shield Blocks (Risk Rejections)": shield_blocks,
            "markdown": md_content
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_payload, f)

        # Print to Terminal
        self._print_terminal(metrics, ml_metrics, report_path)

    def _print_terminal(self, metrics, ml_metrics, path):
        # 1. Trading Table
        t_table = Table(title="Portfolio Analytics", show_header=True, header_style="bold magenta")
        t_table.add_column("Metric", style="cyan")
        t_table.add_column("Value", justify="right")
        
        if "error" in metrics:
            t_table.add_row("Error", metrics["error"])
        else:
            pnl_color = "green" if metrics['total_pnl'] >= 0 else "red"
            t_table.add_row("Total PnL", f"[{pnl_color}][/]")
            t_table.add_row("Win Rate", f"{metrics['win_rate']:.2f}%")
            t_table.add_row("Profit Factor", f"{metrics['profit_factor']:.2f}")
            t_table.add_row("Max Drawdown", f"")
            
        # 2. ML Table
        m_table = Table(title="ML Drift Monitor", show_header=True, header_style="bold blue")
        m_table.add_column("Metric", style="cyan")
        m_table.add_column("Value", justify="right")
        
        if "error" in ml_metrics:
            m_table.add_row("Error", ml_metrics["error"])
        elif ml_metrics.get("total_eval", 0) == 0:
            m_table.add_row("Status", "No High-Prob Data")
        else:
            acc = ml_metrics['realized_accuracy']
            acc_color = "green" if acc >= 50.0 else "bold red"
            m_table.add_row("High-Prob Trades", str(ml_metrics['total_eval']))
            m_table.add_row("Realized Accuracy", f"[{acc_color}]{acc:.2f}%[/]")
            
            if ml_metrics['drift_warning']:
                m_table.add_row("Drift Status", "[bold red blink]WARNING: MODEL DRIFT DETECTED![/]")
            else:
                m_table.add_row("Drift Status", "[bold green]HEALTHY[/]")

        console.print(t_table)
        console.print(m_table)
        console.print(f"\n[bold green]Report saved to: {path}[/]")

if __name__ == "__main__":
    generator = TearsheetGenerator()
    asyncio.run(generator.generate())
