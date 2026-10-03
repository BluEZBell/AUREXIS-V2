import os
import asyncio
from typing import Dict, Any
from src.core.event_bus import EventBus
from src.core.config import setup_logger

logger = setup_logger("ml_oracle")

class MLOracle:
    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self.model = None
        self.mode = "ACTIVE"
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
        self._model_path = os.path.join(project_root, "models", "aurexis_oracle.pkl")

    async def load_model(self):
        """Safely attempt to load the ML model asynchronously."""
        try:
            import joblib
            import sklearn
            
            os.makedirs(os.path.dirname(self._model_path), exist_ok=True)
            if os.path.exists(self._model_path):
                self.model = await asyncio.to_thread(joblib.load, self._model_path)
                self.mode = "ACTIVE"
                logger.info("MLOracle: Model loaded successfully. Machine Learning inference ACTIVE.")
            else:
                logger.warning(f"MLOracle: Model file not found at {self._model_path}.")
        except ImportError:
            logger.warning("MLOracle: joblib or scikit-learn not installed.")
        except Exception as e:
            logger.error(f"MLOracle: Failed to load model ({e}).")

    async def hot_reload(self):
        """Phase 14: Hot-reload the ML model weights mid-flight without dropping MT5 connection."""
        await self.load_model()
        if self.mode == "ACTIVE":
            logger.info("MLOracle: Brain hot-reloaded successfully. Adapted to the latest market regime.")

    def _sync_predict(self, current_features: Dict[str, Any]) -> float:
        if self.model is None:
            return 0.5  # Return neutral instead of crushing signal

        try:
            import numpy as np
            
            # Extract standard indicator features
            features = [
                float(current_features.get('conviction_score', 0.0)),
                float(current_features.get('dxy_val', 0.0)),
                float(current_features.get('us10y_val', 0.0)),
                float(current_features.get('atr_m15', current_features.get('m15_atr', 0.0))),
                float(current_features.get('spread_points', 0.0))
            ]
            
            if hasattr(self.model, 'n_features_in_'):
                if self.model.n_features_in_ >= 6:
                    features.append(float(current_features.get('cumulative_delta', 0.0)))
                if self.model.n_features_in_ >= 7:
                    features.append(float(current_features.get('delta_momentum', 0.0)))
                
            X = np.array([features])
            
            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba(X)
                return float(proba[0][1]) if proba.shape[1] > 1 else float(proba[0][0])
            elif hasattr(self.model, "predict"):
                preds = self.model.predict(X)
                return float(preds[0])
                
        except Exception as e:
            logger.error(f"MLOracle: Prediction failed ({e}). Returning 0.0 score.")
            return 0.0
            
        return 0.0

    async def evaluate_probability(self, current_features: Dict[str, Any]) -> float:
        """
        Runs model prediction. Returns a float (0.0 to 1.0) representing 
        trade win probability.
        """
        return await asyncio.to_thread(self._sync_predict, current_features)
