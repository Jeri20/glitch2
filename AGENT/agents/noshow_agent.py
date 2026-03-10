"""No-show prediction agent backed by a trained model."""

from pathlib import Path

import joblib


class NoShowAgent:
    """Loads a trained no-show model and returns miss probability."""

    def __init__(self, model_path: Path | None = None) -> None:
        default_model_path = Path(__file__).resolve().parents[1] / "models" / "no_show_model.pkl"
        self.model_path = Path(model_path) if model_path is not None else default_model_path

        self.model = None
        if not self.model_path.exists():
            print(f"Warning: Model file not found: {self.model_path}. Using fallback.")
            return

        try:
            self.model = joblib.load(self.model_path)
        except Exception as e:
            print(f"Warning: Failed to load no-show model ({e}). Using fallback.")

    def _predict_probability(self, features_row: list[float]) -> float:
        if self.model is None:
            return 0.15 # Dummy fallback model no-show probability
            
        if hasattr(self.model, "predict_proba"):
            probability = self.model.predict_proba([features_row])[0][1]
            return float(probability)

        # Fallback for models that only expose predict
        prediction = float(self.model.predict([features_row])[0])
        return max(0.0, min(1.0, prediction))

    def predict_no_show(self, features: dict) -> float:
        """Return no-show probability from a features dictionary."""
        row = [
            float(features.get("age", 0.0)),
            float(features.get("sms_received", 0.0)),
            float(features.get("appointment_hour", 0.0)),
            float(features.get("days_between_booking", 0.0)),
        ]
        return self._predict_probability(row)

    def predict(
        self,
        age: float,
        sms_received: int,
        appointment_hour: int,
        days_between_booking: int,
    ) -> float:
        """Backward-compatible prediction signature used by existing pipeline code."""
        return self._predict_probability(
            [
                float(age),
                float(sms_received),
                float(appointment_hour),
                float(days_between_booking),
            ]
        )
