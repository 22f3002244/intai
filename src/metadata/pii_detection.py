import re
import json
import os
import spacy
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from src.ingestion.connectors import load_all

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "pii_report.json")

PATTERNS = {
    "email": re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$"),
    "phone": re.compile(r"^\+?[\d\s().-]{7,}$"),
    "ssn_like": re.compile(r"^\d{3}-\d{2}-\d{4}$"),
    "credit_card": re.compile(r"^\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}$"),
}

nlp = spacy.load("en_core_web_sm")


def classify_by_pattern(series, sample_size=50):
    sample = series.dropna().astype(str).head(sample_size)
    if sample.empty:
        return None
    for label, pattern in PATTERNS.items():
        match_rate = sample.apply(lambda v: bool(pattern.match(v.strip()))).mean()
        if match_rate > 0.7:
            return label
    return None


def classify_by_ner(series, sample_size=20):
    sample = series.dropna().astype(str).head(sample_size)
    if sample.empty:
        return None
    entity_counts = {}
    for value in sample:
        doc = nlp(value)
        for ent in doc.ents:
            entity_counts[ent.label_] = entity_counts.get(ent.label_, 0) + 1
    if not entity_counts:
        return None
    top_label = max(entity_counts, key=entity_counts.get)
    if entity_counts[top_label] / len(sample) > 0.5:
        return top_label
    return None


def classify_column(col_name, series):
    pattern_label = classify_by_pattern(series)
    if pattern_label:
        return pattern_label
    ner_label = classify_by_ner(series)
    if ner_label == "PERSON":
        return "person_name"
    if ner_label == "ORG":
        return "organization"
    if ner_label == "GPE":
        return "location"
    return None


def classify_dataset(name, df):
    classifications = {}
    for col in df.columns:
        label = classify_column(col, df[col])
        if label:
            classifications[col] = label
    return classifications


def run_pii_classification():
    datasets = load_all()
    report = {}
    for name, df in datasets.items():
        classifications = classify_dataset(name, df)
        report[name] = classifications

    with open(OUTPUT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    return report


if __name__ == "__main__":
    report = run_pii_classification()
    for dataset, cols in report.items():
        if cols:
            print(f"{dataset}: {cols}")
