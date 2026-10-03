import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class TelemetryState:
    # Alpha Scorer
    regime: str = "UNKNOWN"
    tick_vwap: float = 0.0
    conviction: float = 0.0
    last_price: float = 0.0
    tuner_state: str = "Baseline"
    
    # Tick Sentinel
    active_positions: int = 0
    floating_pnl: float = 0.0
    ghost_targets: List[str] = field(default_factory=list)
    watchdog_active: bool = False
    watchdog_last_sync: str = "N/A"
    
    # Risk Vault
    daily_drawdown_quota: float = 0.0
    available_margin: float = 0.0
    pyramiding_capability: str = "STANDBY"
    session_start_equity: float = 0.0
    next_milestone_target: float = 0.0
    live_risk_pct: float = 0.0
    
    # Execution Bridge
    broker_online: bool = True
    realtime_spread: float = 0.0
    spread_blackout: bool = False
    recent_latency: float = 0.0
    processing_latency_ms: float = 0.0
    order_latency_ms: float = 0.0
    news_blackout_active: bool = False
    news_blackout_time_left: Optional[float] = None


