import json
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from src.ingestion.connectors import load_all

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "profiles.json")


def profile_column(series):
    return {
        "dtype": str(series.dtype),
        "null_count": int(series.isna().sum()),
        "null_rate": round(float(series.isna().mean()), 4),
        "unique_count": int(series.nunique()),
        "cardinality_ratio": round(float(series.nunique()) / max(len(series), 1), 4),
        "sample_values": series.dropna().astype(str).unique()[:5].tolist(),
    }


def profile_dataset(name, df):
    return {
        "dataset": name,
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": {col: profile_column(df[col]) for col in df.columns},
    }


def profile_all():
    datasets = load_all()
    profiles = {name: profile_dataset(name, df) for name, df in datasets.items()}
    with open(OUTPUT_PATH, "w") as f:
        json.dump(profiles, f, indent=2, default=str)
    return profiles


if __name__ == "__main__":
    profiles = profile_all()
    for name, p in profiles.items():
        print(f"{name}: {p['row_count']} rows, {p['column_count']} columns")
