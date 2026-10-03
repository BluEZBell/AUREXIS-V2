import asyncio
import aiosqlite
import MetaTrader5 as mt5
from datetime import datetime, time, timezone
import os
import csv
from typing import Dict, Any, List, Optional

import src.core.config as config
from src.core.config import run_mt5_task

DB_PATH: str = "campaign_ledger.db"
REPORT_PREFIX: str = "tearsheet_"
JOURNAL_PATH: str = os.path.join("logs", "institutional_journal.csv")

async def generate_tearsheet() -> None:
    print("Starting EOD Tearsheet Generation...")
    
    # 1. Connect to MT5
    def _init_mt5() -> bool:
        if mt5.initialize(path=config.MT5_TERMINAL_PATH):
            return True
        return False

    success: bool = await run_mt5_task(_init_mt5)
    if not success:
        print("Failed to initialize MT5")
        return

    # Define current day boundaries
    now: datetime = datetime.now()
    start_of_day: datetime = datetime.combine(now.date(), time(0, 0, 0))
    end_of_day: datetime = datetime.combine(now.date(), time(23, 59, 59))
    
    # Extract Deals
    def _get_deals() -> Any:
        return mt5.history_deals_get(start_of_day, end_of_day)

    deals: Any = await run_mt5_task(_get_deals)
    if deals is None:
        print(f"Failed to fetch history deals, error code: {mt5.last_error()}")
        deals = []

    gross_profit: float = 0.0
    gross_loss: float = 0.0
    total_commission: float = 0.0
    total_swap: float = 0.0
    net_pnl: float = 0.0
    
    for deal in deals:
        if deal.entry == 1 or deal.entry == 2:  # OUT or INOUT
            total_commission += deal.commission
            total_swap += deal.swap
            deal_net: float = deal.profit + deal.commission + deal.swap
            net_pnl += deal_net
            
            if deal.profit > 0:
                gross_profit += deal.profit
            else:
                gross_loss += abs(deal.profit)

    total_friction: float = total_commission + total_swap

    # Check for 100_PCT_ROI_VAULT in deals or via equity
    vault_triggered: bool = False
    for deal in deals:
        if deal.comment and "VAULT" in deal.comment.upper():
            vault_triggered = True

    # Get Account Info to calculate ROI
    def _get_account_info() -> Any:
        return mt5.account_info()
    
    acc_info: Any = await run_mt5_task(_get_account_info)
    initial_balance: float = float(getattr(config, 'INITIAL_ACCOUNT_BALANCE', 1000.0))
    current_equity: float = acc_info.equity if acc_info else initial_balance
    if current_equity >= initial_balance * 2.0:
        vault_triggered = True

    total_net_roi: float = ((current_equity - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0.0

    # 2. Extract Campaign Ledger Data
    cycles_data: Dict[int, Dict[str, Any]] = {}
    if os.path.exists(DB_PATH):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            try:
                # Fetch IDLE cycles (closed)
                today_ts: float = start_of_day.timestamp()
                
                # Check for columns
                cursor: aiosqlite.Cursor = await db.execute("PRAGMA table_info(cycles)")
                cols_rows = await cursor.fetchall()
                cols: List[str] = [r['name'] for r in cols_rows]
                
                query: str = "SELECT * FROM cycles WHERE state='IDLE' AND cycle_id >= ?"
                cursor = await db.execute(query, (today_ts,))
                rows = await cursor.fetchall()
                
                for row in rows:
                    c_id: int = row['cycle_id']
                    c_pnl: float = row['cycle_pnl'] if 'cycle_pnl' in cols else row['realized_pnl']
                    regime: str = row['regime'] if 'regime' in cols else "UNKNOWN"
                    direction: str = row['direction'] if 'direction' in cols else "UNKNOWN"
                    cycles_data[c_id] = {
                        'pnl': float(c_pnl) if c_pnl is not None else 0.0,
                        'regime': regime,
                        'direction': direction
                    }
            except Exception as e:
                print(f"Error querying {DB_PATH}: {e}")
                
    # 3. Fallback/Supplement with CSV Journal
    if os.path.exists(JOURNAL_PATH):
        try:
            with open(JOURNAL_PATH, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        dt: datetime = datetime.strptime(row['Timestamp_Close'], '%Y-%m-%d %H:%M:%S')
                        if dt.date() == now.date():
                            c_id: int = int(row['Cycle_ID'])
                            c_pnl: float = float(row['Total_Realized_PnL'])
                            regime: str = row['Regime_At_Entry']
                            if c_id not in cycles_data:
                                cycles_data[c_id] = {'pnl': c_pnl, 'regime': regime, 'direction': row['Direction']}
                            else:
                                if cycles_data[c_id]['regime'] == "UNKNOWN":
                                    cycles_data[c_id]['regime'] = regime
                    except Exception:
                        pass
        except Exception as e:
            print(f"Error reading journal: {e}")

    # Calculate Regime Metrics
    regime_stats: Dict[str, Dict[str, Any]] = {
        "CONTRARIAN_MEAN_REVERSION": {"wins": 0, "total": 0, "pnl": 0.0},
        "TRUE_INSTITUTIONAL_TREND": {"wins": 0, "total": 0, "pnl": 0.0},
        "UNKNOWN": {"wins": 0, "total": 0, "pnl": 0.0},
        "TRENDING": {"wins": 0, "total": 0, "pnl": 0.0},
        "SIDEWAYS": {"wins": 0, "total": 0, "pnl": 0.0}
    }

    best_cycle: Optional[Dict[str, Any]] = None
    worst_cycle: Optional[Dict[str, Any]] = None

    for c_id, c_data in cycles_data.items():
        pnl: float = c_data['pnl']
        regime: str = c_data['regime']
        
        if regime not in regime_stats:
            regime_stats[regime] = {"wins": 0, "total": 0, "pnl": 0.0}
            
        regime_stats[regime]["total"] += 1
        regime_stats[regime]["pnl"] += pnl
        if pnl > 0:
            regime_stats[regime]["wins"] += 1
            
        if best_cycle is None or pnl > best_cycle['pnl']:
            best_cycle = {'id': c_id, 'pnl': pnl}
            
        if worst_cycle is None or pnl < worst_cycle['pnl']:
            worst_cycle = {'id': c_id, 'pnl': pnl}

    # Generate Markdown
    md_filename: str = f"{REPORT_PREFIX}{now.strftime('%Y%m%d')}.md"
    
    lines: List[str] = []
    lines.append(f"# Institutional EOD Tearsheet - {now.strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append("## 1. Executive Summary")
    lines.append(f"- **Total Net PnL:** ${net_pnl:.2f}")
    lines.append(f"- **Total Net ROI:** {total_net_roi:.2f}%")
    lines.append(f"- **Current Equity:** ${current_equity:.2f}")
    lines.append(f"- **100% ROI Vault Status:** {'**TRIGGERED** ✅' if vault_triggered else 'Pending'}")
    lines.append("")
    
    lines.append("## 2. Regime Performance Breakdown")
    lines.append("| Regime | Win Rate | Total Cycles | Net PnL |")
    lines.append("|---|---|---|---|")
    for reg, stats in regime_stats.items():
        if stats["total"] > 0:
            wr: float = (stats["wins"] / stats["total"]) * 100
            lines.append(f"| {reg} | {wr:.1f}% | {stats['total']} | ${stats['pnl']:.2f} |")
    if not any(s["total"] > 0 for s in regime_stats.values()):
        lines.append("| N/A | N/A | 0 | $0.00 |")
    lines.append("")
    
    lines.append("## 3. Friction & Efficiency Analysis")
    lines.append(f"- **Gross Profit:** ${gross_profit:.2f}")
    lines.append(f"- **Gross Loss:** ${gross_loss:.2f}")
    lines.append(f"- **Total Commissions Paid:** ${total_commission:.2f}")
    lines.append(f"- **Total Swaps Paid:** ${total_swap:.2f}")
    lines.append(f"- **Total Friction Costs:** ${total_friction:.2f}")
    lines.append(f"- **Average Execution Slippage:** N/A (Requires tick-level order analysis)")
    lines.append("")
    
    lines.append("## 4. Campaign Log")
    if best_cycle:
        lines.append(f"- **Best Campaign Cycle:** ID {best_cycle['id']} (${best_cycle['pnl']:.2f})")
    else:
        lines.append("- **Best Campaign Cycle:** None")
        
    if worst_cycle:
        lines.append(f"- **Worst Campaign Cycle:** ID {worst_cycle['id']} (${worst_cycle['pnl']:.2f})")
    else:
        lines.append("- **Worst Campaign Cycle:** None")
        
    lines.append("")
    lines.append("### Top Cycles")
    sorted_cycles = sorted(cycles_data.items(), key=lambda x: x[1]['pnl'], reverse=True)
    for cycle_tuple in sorted_cycles[:5]:
        lines.append(f"- Cycle {cycle_tuple[0]}: ${cycle_tuple[1]['pnl']:.2f} ({cycle_tuple[1]['regime']})")
        
    lines.append("")
    lines.append("### Bottom Cycles")
    for cycle_tuple in sorted_cycles[-5:]:
        lines.append(f"- Cycle {cycle_tuple[0]}: ${cycle_tuple[1]['pnl']:.2f} ({cycle_tuple[1]['regime']})")

    with open(md_filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    print(f"Successfully generated {md_filename}")
    
    def _shutdown_mt5() -> None:
        mt5.shutdown()
        
    await run_mt5_task(_shutdown_mt5)

if __name__ == "__main__":
    asyncio.run(generate_tearsheet())
