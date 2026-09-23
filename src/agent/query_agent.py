import os
import json
import time
import chromadb
from sentence_transformers import SentenceTransformer
from google import genai
from google.genai.errors import ServerError, APIError

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
CHROMA_HOST = os.environ.get("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", 8001))
COLLECTION_NAME = "data_catalog"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Lazy-initialized singletons — avoids crashes at import time if Chroma/model not ready.
_chroma_client = None
_embedder = None
_gemini_client = None


def _get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    return _chroma_client


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    return _gemini_client


def retrieve_catalog_entries(query, top_k=4):
    collection = _get_chroma_client().get_collection(COLLECTION_NAME)
    query_embedding = _get_embedder().encode([query]).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=top_k)
    return results["documents"][0] if results["documents"] else []


def load_entity_resolution_summary():
    path = os.path.join(DATA_DIR, "entity_resolution_report.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)

def answer_query(user_query, max_retries=3, initial_delay=1.5):
    catalog_matches = retrieve_catalog_entries(user_query)
    dedupe_summary = load_entity_resolution_summary()

    prompt = f"""Relevant dataset catalog entries:
{catalog_matches}

Entity resolution summary:
duplicate customers found: {dedupe_summary.get('duplicate_customers_found', 'not computed')}
cross-source matches found: {dedupe_summary.get('cross_source_matches_found', 'not computed')}

Question: {user_query}

Answer using only the catalog data above."""

    client = _get_gemini_client()
    delay = initial_delay
    last_err = None

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            return response.text
        except (ServerError, APIError) as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                raise RuntimeError(
                    f"Gemini service unavailable after {max_retries} attempts ({e}). "
                    "The model is experiencing high demand; please try again in a few moments or switch GEMINI_MODEL."
                ) from e


if __name__ == "__main__":
    print(answer_query("Which datasets contain customer PII and have poor data quality?"))
