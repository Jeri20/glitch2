"""Generate a synthetic urgency classification dataset."""

from pathlib import Path
import random

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_CSV = PROJECT_ROOT / "urgency_dataset.csv"

HIGH_REASONS = [
    "chest pain",
    "severe breathing difficulty",
    "heart attack symptoms",
    "loss of consciousness",
    "stroke warning signs",
    "uncontrolled bleeding",
    "severe allergic reaction",
    "intense abdominal pain",
    "sudden vision loss",
    "very high blood pressure symptoms",
]

MEDIUM_REASONS = [
    "fever",
    "vomiting",
    "headache",
    "persistent cough",
    "moderate dehydration",
    "ear infection symptoms",
    "skin rash",
    "sore throat",
    "joint pain",
    "migraine",
]

LOW_REASONS = [
    "routine checkup",
    "consultation",
    "follow-up visit",
    "medication refill",
    "diet counseling",
    "annual wellness exam",
    "blood test review",
    "vaccination consultation",
    "minor cold symptoms",
    "general health advice",
]

DETAILS_BY_URGENCY = {
    "HIGH": [
        "since this morning",
        "with rapid worsening",
        "with dizziness",
        "after physical exertion",
        "with sweating",
        "",
    ],
    "MEDIUM": [
        "for two days",
        "with mild weakness",
        "after recent travel",
        "mostly in the evening",
        "with appetite loss",
        "",
    ],
    "LOW": [
        "next available slot",
        "for regular monitoring",
        "as advised by physician",
        "for preventive care",
        "no severe symptoms",
        "",
    ],
}


def _build_reason(urgency: str, rng: random.Random) -> str:
    if urgency == "HIGH":
        base = rng.choice(HIGH_REASONS)
    elif urgency == "MEDIUM":
        base = rng.choice(MEDIUM_REASONS)
    else:
        base = rng.choice(LOW_REASONS)

    detail = rng.choice(DETAILS_BY_URGENCY[urgency])
    return f"{base} {detail}".strip()


def generate_dataset(rows: int = 300, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    urgency_levels = ["HIGH", "MEDIUM", "LOW"]
    weights = [0.30, 0.40, 0.30]

    records = []
    for _ in range(rows):
        urgency = rng.choices(urgency_levels, weights=weights, k=1)[0]
        reason = _build_reason(urgency, rng)
        records.append({"reason": reason, "urgency": urgency})

    return pd.DataFrame(records)


def main() -> None:
    df = generate_dataset(rows=300, seed=42)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved {len(df)} rows to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
