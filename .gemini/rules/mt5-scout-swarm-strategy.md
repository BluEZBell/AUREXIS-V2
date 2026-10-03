---
name: mt5-scout-swarm-strategy
description: Institutional 'Scout & Swarm' (Probe and SAR) offensive trading protocol for the AUREXISV2 MT5 Bot.
---

# 🚀 The Scout & Swarm Protocol (Institutional MT5)

This rule defines the core offensive logic (Probe and Scale + Stop-and-Reverse) used in the `AUREXISV2` MT5 Trading Bot. Always adhere to these structural constraints when modifying `alpha_harvester.py`, `bridge.py`, or `risk_manager.py`.

## 1. Risk and Margin (The 1:2 Ratio)
* **Scout Phase (Probe):** The initial exploratory position (ไม้ A) must be small (e.g., `0.01 Lot` for a $100 account). Controlled via `risk_manager.py`.
* **Swarm Phase (Scale/SAR):** The follow-up positions must heavily outweigh the Scout (e.g., `0.02 Lot x 3`). 
* **Leverage Prerequisite:** This strategy assumes a high-leverage account (1:888 or 1:1000). A $100 account opening ~0.07 total lots requires at least this leverage to avoid `Margin Shield Errors`.

## 2. Execution Logic (alpha_harvester.py)
* **Case 1 (Trend / ตามกระแส):**
  If Scout profit reaches `+$1.00`, immediately publish 3x `SWARM_TREND` signals in the SAME direction to scale in.
* **Case 2 (Reversal / สวนกระแส / SAR):**
  If Scout profit drops to `-$1.50`, immediately CLOSE the Scout, and publish 3x `SWARM_REVERSAL` signals in the OPPOSITE direction.
* **Exit Strategy:**
  If total profit hits `+$5.00` OR momentum changes (e.g., `m15_trend` flips against the Swarm direction), close all positions simultaneously and reset.
* **Ping-Pong Circuit Breaker:**
  If the strategy suffers 3 consecutive losses (`loss_streak >= 3`), force a 15-minute cooldown (`current_time + 900.0`) to avoid Whipsaw traps.

## 3. Bridge Overrides (bridge.py)
The execution bridge usually contains defensive constraints ("Doomsday Shields"). Swarm signals must bypass these to function:
* **Spacing Lock Bypass:** Signals with `strategy_id` of `"SWARM_TREND"` or `"SWARM_REVERSAL"` must return `True` before the Pyramiding Spacing check.
* **Machine-Gun Lock Bypass:** Swarm signals must bypass the 3-second order limit (`time.time() - self._last_order_time < 3.0`), otherwise consecutive swarm requests will be dropped.
* **API Spam Prevention:** Although the lock is bypassed, always add a slight asynchronous delay (`await asyncio.sleep(0.1)`) between consecutive `event_bus.publish` calls to prevent MT5 `Terminal: Call failed` errors.

## 4. Black Swan / News Warning
This system is 100% offensive with no "defensive" stop-loss logic outside of SAR and a -$10 swarm panic cut. **Never operate this protocol during major economic news (Red Folder: NFP, CPI)**, as slippage can bypass the soft stops and cause an instant Stop Out (Margin Call).
