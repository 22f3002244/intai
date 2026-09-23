import re
import json
import os
import spacy

from src.ingestion.connectors import load_all

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "pii_report.json")

PATTERNS = {
    "email": re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$"),
    "ssn_like": re.compile(r"^\d{3}-\d{2}-\d{4}$"),
    "credit_card": re.compile(r"^\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}$"),
    "phone": re.compile(r"^\+?[\d\s().-]{7,}$"),
}

# Fix #9: increase sample sizes for more reliable classification.
PATTERN_SAMPLE_SIZE = 100   # was 50
NER_SAMPLE_SIZE = 50        # was 20
PATTERN_MATCH_THRESHOLD = 0.7
NER_MATCH_THRESHOLD = 0.5

nlp = spacy.load("en_core_web_sm")


def classify_by_pattern(series, sample_size=PATTERN_SAMPLE_SIZE):
    """Return (label, confidence) or (None, 0.0) if no pattern matches."""
    sample = series.dropna().astype(str).head(sample_size)
    if sample.empty:
        return None, 0.0
    for label, pattern in PATTERNS.items():
        match_rate = sample.apply(lambda v: bool(pattern.match(v.strip()))).mean()
        if match_rate >= PATTERN_MATCH_THRESHOLD:
            return label, round(float(match_rate), 4)
    return None, 0.0


def classify_by_ner(series, sample_size=NER_SAMPLE_SIZE):
    """Return (label, confidence) or (None, 0.0) if no NER entity dominates."""
    sample = series.dropna().astype(str).head(sample_size)
    if sample.empty:
        return None, 0.0
    entity_counts: dict[str, int] = {}
    for value in sample:
        doc = nlp(value)
        for ent in doc.ents:
            entity_counts[ent.label_] = entity_counts.get(ent.label_, 0) + 1
    if not entity_counts:
        return None, 0.0
    top_label = max(entity_counts, key=entity_counts.get)
    confidence = entity_counts[top_label] / len(sample)
    if confidence >= NER_MATCH_THRESHOLD:
        return top_label, round(confidence, 4)
    return None, 0.0


def classify_column(col_name, series):
    """
    Return a dict with 'type' and 'confidence', or None if no PII detected.
    Fix #9: confidence is now stored in the output, not silently discarded.
    """
    label, confidence = classify_by_pattern(series)
    if label:
        return {"type": label, "confidence": confidence, "method": "pattern"}

    ner_label, ner_confidence = classify_by_ner(series)
    mapping = {"PERSON": "person_name", "ORG": "organization", "GPE": "location"}
    if ner_label in mapping:
        return {"type": mapping[ner_label], "confidence": ner_confidence, "method": "ner"}

    return None


def classify_dataset(name, df):
    classifications = {}
    for col in df.columns:
        result = classify_column(col, df[col])
        if result:
            classifications[col] = result
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
