"""Preprocess cleaned appointment data for no-show model training."""

from pathlib import Path
import re

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = Path(r"C:\Users\D.POOJITHA\Downloads\AGENT\training\cleaned_appointments.csv")
OUTPUT_CSV = Path(r"C:\Users\D.POOJITHA\Downloads\AGENT\training\noshow_training_data.csv")


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str:
    normalized_to_original = {_normalize(col): col for col in df.columns}
    for candidate in candidates:
        key = _normalize(candidate)
        if key in normalized_to_original:
            return normalized_to_original[key]
    raise KeyError(f"None of these columns were found: {candidates}")


def _to_binary_noshow(series: pd.Series) -> pd.Series:
    mapped = (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map(
            {
                "yes": 1,
                "no": 0,
                "1": 1,
                "0": 0,
                "true": 1,
                "false": 0,
            }
        )
    )

    unresolved = series[mapped.isna()].dropna().unique().tolist()
    if unresolved:
        raise ValueError(f"Unexpected No-show values: {unresolved}")

    return mapped


def preprocess(input_csv: Path = INPUT_CSV, output_csv: Path = OUTPUT_CSV) -> Path:
    df = pd.read_csv(input_csv)

    no_show_col = _find_column(df, ["No-show", "no_show", "noshow"])
    scheduled_col = _find_column(df, ["ScheduledDay", "scheduledday", "scheduled_day"])
    appointment_col = _find_column(df, ["AppointmentDay", "appointmentday", "appointment_day"])
    age_col = _find_column(df, ["Age", "age"])
    sms_col = _find_column(df, ["SMS_received", "sms_received", "smsreceived"])

    # 1) Convert No-show to binary (1 = no show, 0 = show)
    df["No-show"] = _to_binary_noshow(df[no_show_col])

    # 2) Convert ScheduledDay and AppointmentDay to datetime
    df[scheduled_col] = pd.to_datetime(df[scheduled_col], errors="coerce", utc=True)
    df[appointment_col] = pd.to_datetime(df[appointment_col], errors="coerce", utc=True)

    # 3) Create days_between_booking
    df["days_between_booking"] = (
        df[appointment_col].dt.normalize() - df[scheduled_col].dt.normalize()
    ).dt.days

    # 4) Extract appointment_hour
    df["appointment_hour"] = df[appointment_col].dt.hour

    # 5) Keep required columns
    processed = pd.DataFrame(
        {
            "Age": pd.to_numeric(df[age_col], errors="coerce"),
            "SMS_received": pd.to_numeric(df[sms_col], errors="coerce"),
            "appointment_hour": df["appointment_hour"],
            "days_between_booking": df["days_between_booking"],
            "No-show": df["No-show"],
        }
    )

    processed = processed.dropna().copy()
    processed["Age"] = processed["Age"].astype(int)
    processed["SMS_received"] = processed["SMS_received"].astype(int)
    processed["appointment_hour"] = processed["appointment_hour"].astype(int)
    processed["days_between_booking"] = processed["days_between_booking"].astype(int)
    processed["No-show"] = processed["No-show"].astype(int)

    processed.to_csv(output_csv, index=False)
    return output_csv


def main() -> None:
    output_path = preprocess()
    print(f"Saved processed dataset to: {output_path}")


if __name__ == "__main__":
    main()
