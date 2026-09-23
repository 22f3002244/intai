import hashlib
import json
import os
import chromadb
from sentence_transformers import SentenceTransformer

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
PROFILES_PATH = os.path.join(DATA_DIR, "profiles.json")
QUALITY_PATH = os.path.join(DATA_DIR, "quality_report.json")
PII_PATH = os.path.join(DATA_DIR, "pii_report.json")
HASH_CACHE_PATH = os.path.join(DATA_DIR, "catalog_index_hash.json")

CHROMA_HOST = os.environ.get("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", 8001))
COLLECTION_NAME = "data_catalog"


# ── Staleness helpers (Fix #15) ────────────────────────────────────────────────

def _compute_data_hash() -> str:
    """SHA-256 of the combined content of the three pipeline output files."""
    h = hashlib.sha256()
    for path in (PROFILES_PATH, QUALITY_PATH, PII_PATH):
        if os.path.exists(path):
            with open(path, "rb") as f:
                h.update(f.read())
    return h.hexdigest()


def _read_cached_hash() -> str | None:
    if not os.path.exists(HASH_CACHE_PATH):
        return None
    with open(HASH_CACHE_PATH) as f:
        return json.load(f).get("hash")


def _write_cached_hash(digest: str):
    with open(HASH_CACHE_PATH, "w") as f:
        json.dump({"hash": digest}, f)


def is_index_stale() -> bool:
    """Return True if any pipeline output has changed since the last index build."""
    return _compute_data_hash() != _read_cached_hash()


# ── Catalog entry builder ──────────────────────────────────────────────────────

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
        dup_rows = profile.get("duplicate_row_count", 0)

        def _col_desc(col, info):
            pii_tag = ""
            if col in pii_cols:
                pii_meta = pii_cols[col]
                pii_tag = f", PII: {pii_meta.get('type', pii_meta)} ({pii_meta.get('confidence', '?'):.0%})" \
                    if isinstance(pii_meta, dict) else f", PII: {pii_meta}"
            return f"{col} ({info['dtype']}{pii_tag})"

        columns_desc = ", ".join(_col_desc(col, info) for col, info in profile["columns"].items())
        description = (
            f"Dataset '{name}' has {profile['row_count']} rows and {profile['column_count']} columns. "
            f"Data quality score: {quality_score}/100. "
            f"Duplicate rows: {dup_rows}. "
            f"Columns: {columns_desc}. "
            f"Contains PII columns: {list(pii_cols.keys()) if pii_cols else 'none detected'}."
        )
        entries.append({"id": name, "text": description})
    return entries


# ── Index builder ──────────────────────────────────────────────────────────────

def build_index(force: bool = False):
    """
    Build (or rebuild) the ChromaDB catalog index.

    Fix #15: skips re-embedding if the pipeline output files haven't changed
    since the last run. Pass force=True to bypass the staleness check.
    """
    current_hash = _compute_data_hash()

    if not force and current_hash == _read_cached_hash():
        print("Catalog index is up-to-date — skipping re-embedding. Use --force to override.")
        return

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
    _write_cached_hash(current_hash)
    print(f"Indexed {len(entries)} dataset descriptions into '{COLLECTION_NAME}'")


if __name__ == "__main__":
    import sys
    build_index(force="--force" in sys.argv)
