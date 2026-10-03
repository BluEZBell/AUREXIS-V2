import asyncio
import logging
from typing import Dict, Any, List

import src.core.config as config

logger = logging.getLogger("adaptive_tuner")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class AdaptiveTuner:
    """
    Adaptive Feedback Tuner (Alpha Decay adapter).
    Listens for TRADE_CLOSED events, calculates rolling MFE/MAE ratio.
    Automatically tightens constraints in AlphaScorer if the ratio decays,
    and relaxes them when the edge recovers.
    """
    def __init__(self, alpha_scorer: Any, telemetry_state: Any, window_size: int = 20) -> None:
        self.alpha_scorer = alpha_scorer
        self.telemetry_state = telemetry_state
        self.window_size = window_size
        self._recent_trades: List[Dict[str, Any]] = []
        self._trigger_event = asyncio.Event()
        self._running = False
        self._task = None

    def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._tune_loop())
        logger.info("AdaptiveTuner started.")
        
    def stop(self) -> None:
        self._running = False
        self._trigger_event.set()
        if self._task:
            self._task.cancel()
        logger.info("AdaptiveTuner stopped.")


    def on_trade_closed(self, trade_data: Dict[str, Any]) -> None:
        """
        Triggered synchronously by TelemetryLogger when a TRADE_CLOSED event occurs.
        Uses asyncio.Event to trigger the evaluation loop in a non-blocking, thread-safe manner.
        """
        self._recent_trades.append(trade_data)
        if len(self._recent_trades) > self.window_size:
            self._recent_trades.pop(0)
        self._trigger_event.set()

    async def _tune_loop(self):
        while self._running:
            await self._trigger_event.wait()
            if not self._running:
                break
            self._trigger_event.clear()
            self._evaluate_performance()

    def _evaluate_performance(self) -> None:
        if not self._recent_trades:
            return
            
        total_mfe = sum(t.get("mfe", t.get("MFE", 0.0)) for t in self._recent_trades)
        total_mae = sum(t.get("mae", t.get("MAE", 0.0)) for t in self._recent_trades)
        
        if total_mae <= 0.0:
            ratio = float('inf') if total_mfe > 0 else 1.0
        else:
            ratio = total_mfe / total_mae
            
        if ratio < 1.0:
            self._tighten_constraints(ratio)
        else:
            self._relax_constraints(ratio)

    def _tighten_constraints(self, ratio: float) -> None:
        if self.telemetry_state:
            self.telemetry_state.tuner_state = "TIGHTENED"
        current_threshold = getattr(self.alpha_scorer, 'baseline_conviction_threshold', 50.0)
        new_threshold = min(60.0, current_threshold + 5.0)
        self.alpha_scorer.baseline_conviction_threshold = new_threshold
        logger.info(f"AdaptiveTuner: Tightened conviction to {new_threshold:.1f} (ratio {ratio:.2f})")

    def _relax_constraints(self, ratio: float) -> None:
        if self.telemetry_state:
            self.telemetry_state.tuner_state = "RELAXED"
        current_threshold = getattr(self.alpha_scorer, 'baseline_conviction_threshold', 50.0)
        new_threshold = max(20.0, current_threshold - 5.0)
        self.alpha_scorer.baseline_conviction_threshold = new_threshold
        logger.info(f"AdaptiveTuner: Relaxed conviction to {new_threshold:.1f} (ratio {ratio:.2f})")
