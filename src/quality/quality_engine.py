import json
import os
import pandas as pd

PROFILES_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "profiles.json")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "quality_report.json")

NULL_RATE_WARN = 0.05
NULL_RATE_FAIL = 0.15
LOW_CARDINALITY_ID_THRESHOLD = 0.9  # id-like columns should be near-unique
OUTLIER_IQR_MULTIPLIER = 1.5
OUTLIER_RATE_WARN = 0.05


def score_column(col_name, col_profile):
    issues = []
    score = 100

    # Null-rate check
    if col_profile["null_rate"] >= NULL_RATE_FAIL:
        issues.append(f"high null rate ({col_profile['null_rate']:.1%})")
        score -= 40
    elif col_profile["null_rate"] >= NULL_RATE_WARN:
        issues.append(f"moderate null rate ({col_profile['null_rate']:.1%})")
        score -= 15

    # ID-column uniqueness check
    looks_like_id = "id" in col_name.lower()
    if looks_like_id and col_profile["cardinality_ratio"] < LOW_CARDINALITY_ID_THRESHOLD:
        issues.append(f"id-like column with low uniqueness ({col_profile['cardinality_ratio']:.2f})")
        score -= 25

    # Fix #14: outlier check for numeric columns.
    outlier_info = col_profile.get("outlier_rate")
    if outlier_info is not None and outlier_info >= OUTLIER_RATE_WARN:
        issues.append(f"high outlier rate ({outlier_info:.1%} of values outside IQR×{OUTLIER_IQR_MULTIPLIER})")
        score -= 15

    return max(score, 0), issues


def score_dataset(dataset_profile):
    column_scores = {}
    all_issues = []
    for col_name, col_profile in dataset_profile["columns"].items():
        score, issues = score_column(col_name, col_profile)
        column_scores[col_name] = {"score": score, "issues": issues}
        if issues:
            all_issues.append({"column": col_name, "issues": issues})

    dataset_score = round(
        sum(c["score"] for c in column_scores.values()) / max(len(column_scores), 1), 1
    )
    return {
        "dataset": dataset_profile["dataset"],
        "overall_score": dataset_score,
        "duplicate_row_count": dataset_profile.get("duplicate_row_count", 0),
        "duplicate_row_rate": dataset_profile.get("duplicate_row_rate", 0.0),
        "column_scores": column_scores,
        "flagged_issues": all_issues,
    }


def run_quality_checks():
    with open(PROFILES_PATH) as f:
        profiles = json.load(f)

    report = {name: score_dataset(profile) for name, profile in profiles.items()}
    with open(OUTPUT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    return report


if __name__ == "__main__":
    report = run_quality_checks()
    for name, r in report.items():
        dup_note = f", {r['duplicate_row_count']} duplicate rows" if r["duplicate_row_count"] else ""
        print(f"{name}: quality score {r['overall_score']}/100, {len(r['flagged_issues'])} flagged columns{dup_note}")
