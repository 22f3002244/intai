import json
import os
import numpy as np
import pandas as pd

from src.ingestion.connectors import load_all

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "profiles.json")

OUTLIER_IQR_MULTIPLIER = 1.5


def _count_outliers(series: pd.Series) -> tuple[int, float]:
    """Return (outlier_count, outlier_rate) using IQR method for numeric columns."""
    if not pd.api.types.is_numeric_dtype(series):
        return 0, 0.0
    clean = series.dropna()
    if len(clean) < 4:  # need at least 4 values to compute meaningful IQR
        return 0, 0.0
    q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return 0, 0.0
    lower, upper = q1 - OUTLIER_IQR_MULTIPLIER * iqr, q3 + OUTLIER_IQR_MULTIPLIER * iqr
    outlier_count = int(((clean < lower) | (clean > upper)).sum())
    return outlier_count, round(outlier_count / len(clean), 4)


def profile_column(series: pd.Series) -> dict:
    outlier_count, outlier_rate = _count_outliers(series)
    return {
        "dtype": str(series.dtype),
        "null_count": int(series.isna().sum()),
        "null_rate": round(float(series.isna().mean()), 4),
        "unique_count": int(series.nunique()),
        "cardinality_ratio": round(float(series.nunique()) / max(len(series), 1), 4),
        "outlier_count": outlier_count,       # Fix #14: new field for quality engine
        "outlier_rate": outlier_rate,          # Fix #14: new field for quality engine
        "sample_values": series.dropna().astype(str).unique()[:5].tolist(),
    }


def profile_dataset(name: str, df: pd.DataFrame) -> dict:
    # Fix #14: count exact duplicate rows at the dataset level.
    dup_count = int(df.duplicated().sum())
    return {
        "dataset": name,
        "row_count": len(df),
        "column_count": len(df.columns),
        "duplicate_row_count": dup_count,
        "duplicate_row_rate": round(dup_count / max(len(df), 1), 4),
        "columns": {col: profile_column(df[col]) for col in df.columns},
    }


def profile_all() -> dict:
    datasets = load_all()
    profiles = {name: profile_dataset(name, df) for name, df in datasets.items()}
    with open(OUTPUT_PATH, "w") as f:
        json.dump(profiles, f, indent=2, default=str)
    return profiles


if __name__ == "__main__":
    profiles = profile_all()
    for name, p in profiles.items():
        dup_note = f", {p['duplicate_row_count']} duplicate rows" if p["duplicate_row_count"] else ""
        print(f"{name}: {p['row_count']} rows, {p['column_count']} columns{dup_note}")
