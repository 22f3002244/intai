import json
import os
import chromadb
from sentence_transformers import SentenceTransformer

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
PROFILES_PATH = os.path.join(DATA_DIR, "profiles.json")
QUALITY_PATH = os.path.join(DATA_DIR, "quality_report.json")
PII_PATH = os.path.join(DATA_DIR, "pii_report.json")

CHROMA_HOST = os.environ.get("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", 8001))
COLLECTION_NAME = "data_catalog"


def build_catalog_entries():
    with open(PROFILES_PATH) as f:
        profiles = json.load(f)
    with open(QUALITY_PATH) as f:
        quality = json.load(f)
    with open(PII_PATH) as f:
        pii = json.load(f)

    entries = []
    for name, profile in profiles.items():
        pii_cols = pii.get(name, {})
        quality_score = quality.get(name, {}).get("overall_score", "unknown")
        columns_desc = ", ".join(
            f"{col} ({info['dtype']}{', PII: ' + pii_cols[col] if col in pii_cols else ''})"
            for col, info in profile["columns"].items()
        )
        description = (
            f"Dataset '{name}' has {profile['row_count']} rows and {profile['column_count']} columns. "
            f"Data quality score: {quality_score}/100. "
            f"Columns: {columns_desc}. "
            f"Contains PII columns: {list(pii_cols.keys()) if pii_cols else 'none detected'}."
        )
        entries.append({"id": name, "text": description})
    return entries


def build_index():
    client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    collection = client.get_or_create_collection(COLLECTION_NAME)
    embedder = SentenceTransformer("all-MiniLM-L6-v2")

    entries = build_catalog_entries()
    embeddings = embedder.encode([e["text"] for e in entries]).tolist()

    collection.upsert(
        ids=[e["id"] for e in entries],
        documents=[e["text"] for e in entries],
        embeddings=embeddings,
    )
    print(f"Indexed {len(entries)} dataset descriptions into '{COLLECTION_NAME}'")


if __name__ == "__main__":
    build_index()
