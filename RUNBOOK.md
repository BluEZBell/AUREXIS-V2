# dY"~ AUREXIS V2: Institutional Runbook

## 1. Architecture Overview
AUREXIS V2 is a fully autonomous, asynchronous, event-driven trading engine built on Python and MetaTrader 5 (MT5). It is designed to operate seamlessly in a proprietary trading environment under a strict **"100% Daily Flip"** mandate. 

The architecture consists of four core pillars working in lockstep without blocking the I/O event loop:
1. **Async MT5 Bridge**: The raw execution engine.
2. **Tick Sentinel (Risk Vault)**: The relentless guardian that enforces strict trailing stops, time-decay filters, and MFE-based giveback control.
3. **Alpha Harvester (The Scorer)**: The brain that predicts short-term directional movement and evaluates Multi-Factor Chop Scores.
4. **Telegram Telemetry (The Communicator)**: The asynchronous pipeline for logging events and accepting remote kill-switch commands.

### The "100% Daily Flip" Methodology (Challenge Mode)
The engine utilizes a strategy known as the **Hyper-Aggressive Asymmetric Snowball**. To scale a micro-account (e.g., $100 to $200 in one day) while ensuring capital preservation, AUREXIS isolates risk through **Free-Roll Pyramiding**:
* The engine shoots a single **PROBE** trade.
* If the PROBE achieves True Break-Even (Risk drops to $0), the system identifies an `active_risk_count == 0` state.
* The system is then unleashed to fire aggressive **SET** orders (Pyramiding) sequentially to snowball profits into the target.
* If conviction scores are overwhelmingly high (>= 80), the Pyramiding spacing is tightly condensed to maximize leverage during a market breakout.

### The 30-Case State Machine & Regime Radar
AUREXIS V2 implements a rigorously decoupled, 30-Case Asynchronous State Machine to handle every execution edge case without monolithic loops:
* **`HOLD_RECOVERY` (Case 25):** If the Swarm reaches full capacity (3 positions) but the aggregate P/L is negative, the Harvester blocks all new entries. It relies exclusively on the Sentinel's Virtual SL or Target Hit for resolution, preventing duplicate orders.
* **`CLOSE_RECOVERY` (Case 26):** If the MT5 API drops packets during a mass liquidation (Target Hit), the system enters `CLOSE_RECOVERY`. The Harvester persistently verifies `mt5.positions_get` and re-dispatches `CLOSE` OrderEvents until Ghost Positions are 100% eradicated.
* **`WARNING_WAIT` (Cases 4, 14, 17):** If price reverses slightly but does not breach the 0.20 ATR Virtual SL Kill-Zone, the Sentinel broadcasts `WARNING_STOP_ADD`. The Harvester halts Pyramiding (`WARNING_WAIT`), resuming only when momentum (ADX >= 22) returns.
* **Capital Velocity Chaining (Cases 19, 20, 29):** When a reversal confirms (Scout Fail), the engine instantly liquidates the old cycle and seamlessly chains a new cycle by firing a `PROBE` in the opposite direction. No downtime.
* **Event Collision Resolution (Case 11):** The `TickSentinel` evaluates mathematical edge cases with absolute priority. A `TargetHitEvent` overrides any simultaneous `StructuralTrendEvent` (Reversal), instantly bypassing the Kill checks to prevent `CLOSE` order collisions at the broker level.
* **Multi-Factor Chop Radar:** Replaces static ADX sideways detection with a dynamic 0-5 Chop Score evaluating 5 binary conditions:
  - ADX < 18
  - RSI between 45-55
  - EMA20/50 distance < 0.15 ATR
  - 10-candle M5 Range < 0.80 M15_ATR
  - Whipsaw count >= 3 direction changes in 10 candles
  A score of **>= 3** triggers `CHOP_WARNING`, neutralizing Conviction Scores and blocking new SETs. A score of **>= 4** triggers `CHOP_LOCK`, halting all cycle generation. The engine only unlocks when the **Breakout Score** reaches >= 4 (requiring structural breakout, ADX > 20 rising, RSI trending, and EMA expansion).

## 2. Deployment
AUREXIS is designed to run in a headless (no GUI) environment on a VPS or dedicated server.

### Starting the Engine
Do not execute `main.py` directly. Instead, invoke the PowerShell deployment watchdog. The watchdog ensures the engine stays alive, capturing non-zero exits and restarting the bot within 5 seconds if a crash occurs.
```powershell
.\run_aurexis_watchdog.ps1
```
All system logs and errors are routed to `logs/watchdog.log`, `logs/aurexis_out.log`, and `logs/aurexis_err.log`.

### Diagnostics & Analytics
* **EOD Analytics (`ops_eod_report.py`)**: Generates a professional tearsheet calculating Expected Value (EV), win rates, and Regime-Based PnL from the `institutional_journal.csv`.
* **Database Backup (`ops_backup_ledger.py`)**: Securely copies the WAL-enabled SQLite database to `db/backups/` via `asyncio.to_thread`.
* **Health Check (`ops_health_check.py`)**: Verifies margin, ping latency, and database integrity before Live Ignition.

## 3. Risk Management
AUREXIS handles risk dynamically, removing the emotional burden from the trader.

* **Micro-Account Aggression (5% Base Risk)**: The lot sizing module correctly calculates base volume utilizing MT5's exact contract parameters. It ensures EXACTLY 5% monetary risk on each PROBE.
* **1.0 ATR Hard SL Cap**: To strictly mitigate severe residential network jitter, the Hard Stop Loss is mathematically clamped to a maximum of `1.0 ATR` in the broker's system.
* **Ultra-Fast Break-Even**: When a position achieves 150 points in profit, the Tick Sentinel slams the Stop Loss precisely to True Break-Even + 2 pips.
* **Time-Decay Kills**: Trades that fail to launch (profit < 30 points) after 15 minutes of exposure are relentlessly liquidated by the Sentinel to free up capital.
* **Structural Virtual SL**: If the M15 higher-timeframe structure aggressively flips against an open trade, the Sentinel initiates a tactical liquidation, dodging the hard Stop Loss.

### MFE Vault & Giveback Control
The Sentinel tracks the Maximum Favorable Excursion (MFE) tick-by-tick and applies dynamic profit protection tiers (parameterized dynamically based on the current PROBE lot size value):
* **Level 1 (Proof of Profit):** `MFE >= $1_equiv`. Activates profit attempt tracking.
* **Level 2 (Giveback Control / Recovery Test):** `MFE >= $2_equiv`. If PnL drops to $0, a 15-minute `RECOVERY_TEST` begins. If the market fails to reclaim Level 1 within 3 M5 candles, the cycle is liquidated via Target Hit.
* **Level 3 (Strong Protection / Profit Floor):** `MFE >= $4_equiv`. Establishes a strict, unbreakable profit floor at Level 1.
* **Ruthless Hard Exit:** The ultimate SL Dragging eradication. If MFE reaches Level 1 but the current PnL plummets to `-$4_equiv`, the system executes an instant, Ruthless Close All, preempting the Doomsday 1.0 ATR Hard SL entirely.

## 4. Telemetry & Commands
AUREXIS uses an async `aiohttp` broadcaster to dispatch crucial events to the Fund Manager's Telegram.

### Remote Kill-Switch
If a Black Swan event occurs (e.g., unexpected CPI miss, geopolitical conflict) that the standard momentum algorithms cannot calculate, the Fund Manager can immediately intervene:
1. Open the connected Telegram Chat.
2. Send the message `/panic` or `/halt`.
3. The engine's async polling loop will immediately dispatch a `CommandEvent(action="PANIC_HALT")`.
4. The MT5 Bridge will forcefully liquidate all positions, cancel all pending orders, and lock down the execution bridge.
5. A confirmation message ("dYs" PANIC HALT INITIATED") will be dispatched back to Telegram.

## 5. Repository Integrity
To preserve the structural integrity of the execution environment across multiple VPS instances, runtime artifacts are explicitly ignored in version control via `.gitignore`.
* `logs/*.log` and `.csv` are strictly local.
* `db/*.db`, `db/*.db-wal`, `db/*.db-shm` are excluded to prevent accidental lock states or corruption when pulling updates.
Empty `.gitkeep` files preserve the directory structure. 

---
*Engine Version: AUREXIS V2 Institutional Grade*
*Mode: Unrestricted Snowball (MFE Vault & Multi-Factor Chop Radar Active)*
