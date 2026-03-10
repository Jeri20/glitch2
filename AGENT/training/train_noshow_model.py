"""Train a no-show prediction model from preprocessed appointment data."""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split


PROJECT_ROOT = Path(r"C:\Users\D.POOJITHA\Downloads\AGENT\training")
DATA_PATH = PROJECT_ROOT / "noshow_training_data.csv"
MODEL_PATH = PROJECT_ROOT / "models" / "no_show_model.pkl"

FEATURE_COLUMNS = [
    "Age",
    "SMS_received",
    "appointment_hour",
    "days_between_booking",
]
TARGET_COLUMN = "No-show"


def train() -> tuple[GradientBoostingClassifier, float]:
    df = pd.read_csv(DATA_PATH)

    missing = [col for col in FEATURE_COLUMNS + [TARGET_COLUMN] if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    # 1) Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    # 2) Train Gradient Boosting classifier (replacement for Logistic Regression)
    model = GradientBoostingClassifier(random_state=42)
    model.fit(X_train, y_train)

    # 3) Print accuracy
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Accuracy: {accuracy:.4f}")

    # 4) Save model using joblib
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"Model saved to: {MODEL_PATH}")

    return model, accuracy


if __name__ == "__main__":
    train()
