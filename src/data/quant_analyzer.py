import os
import sys
import pandas as pd
import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

def analyze_ticks(file_path: str = "live_ticks.csv") -> None:
    console = Console()
    
    if not os.path.exists(file_path):
        console.print(f"[red]Error: {file_path} not found. Ensure the Tick Vault has written data.[/red]")
        sys.exit(1)
        
    try:
        # Task 1: Tick Data Ingestion with robust error handling
        # Using on_bad_lines='skip' to drop completely malformed rows (pandas >= 1.3)
        try:
            df = pd.read_csv(file_path, on_bad_lines='skip')
        except pd.errors.EmptyDataError:
            console.print(f"[yellow]Warning: {file_path} is completely empty. No data to analyze.[/yellow]")
            return
        
        if df.empty:
            console.print(f"[yellow]Warning: {file_path} is empty or too short. No data to analyze.[/yellow]")
            return
            
        # Ensure correct column types and handle corrupted rows
        expected_cols = ["Timestamp", "Bid", "Ask", "Spread", "Volume"]
        for col in expected_cols:
            if col not in df.columns:
                console.print(f"[red]Error: Missing expected column '{col}' in {file_path}. Found columns: {df.columns.tolist()}[/red]")
                sys.exit(1)
                
        # Coerce to numeric to drop corrupted data
        for col in expected_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        df = df.dropna()
        
        if df.empty:
            console.print(f"[yellow]Warning: {file_path} contains no valid numeric rows after cleaning.[/yellow]")
            return
            
        # Task 2: Micro-Structure Metrics Calculation
        mean_spread: float = float(df["Spread"].mean())
        median_spread: float = float(df["Spread"].median())
        max_spread: float = float(df["Spread"].max())
        
        # Tick Velocity (ticks per minute)
        min_ts: float = float(df["Timestamp"].min())
        max_ts: float = float(df["Timestamp"].max())
        time_diff_sec: float = max_ts - min_ts
        time_diff_min: float = time_diff_sec / 60.0
        
        total_ticks: int = len(df)
        
        if time_diff_min > 0:
            tick_velocity: float = total_ticks / time_diff_min
        else:
            tick_velocity = 0.0
            
        # Task 3: Institutional Terminal Reporting
        table = Table(title="Microstructure Analysis Report", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", justify="right", style="green")
        table.add_column("Description", style="dim")
        
        table.add_row("Mean Spread", f"{mean_spread:.5f}", "Average spread over the session")
        table.add_row("Median Spread", f"{median_spread:.5f}", "Baseline broker spread (removes outliers)")
        table.add_row("Max Spread Spike", f"{max_spread:.5f}", "Peak spread expansion / predatory markup")
        table.add_row("Tick Velocity", f"{tick_velocity:.2f}", "Average ticks per minute (volatility)")
        table.add_row("Total Ticks", f"{total_ticks}", "Total valid ticks analyzed")
        table.add_row("Session Length", f"{time_diff_min:.2f} min", "Total time span of the dataset")
        
        console.print(Panel.fit(table, title="AUREXIS Quant Alpha", border_style="blue"))
        
    except PermissionError:
        console.print(f"[yellow]Warning: {file_path} is currently locked by another process (likely Tick Vault). Please try again.[/yellow]")
    except Exception as e:
        console.print(f"[red]Fatal Error analyzing {file_path}: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    analyze_ticks()
