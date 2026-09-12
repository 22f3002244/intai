import os
import json
import chromadb
from sentence_transformers import SentenceTransformer
from google import genai
from google.genai import types

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
CHROMA_HOST = os.environ.get("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", 8001))
COLLECTION_NAME = "data_catalog"

chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
embedder = SentenceTransformer("all-MiniLM-L6-v2")

gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def retrieve_catalog_entries(query, top_k=4):
    collection = chroma_client.get_collection(COLLECTION_NAME)
    query_embedding = embedder.encode([query]).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=top_k)
    return results["documents"][0] if results["documents"] else []


def load_entity_resolution_summary():
    path = os.path.join(DATA_DIR, "entity_resolution_report.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def answer_query(user_query):
    catalog_matches = retrieve_catalog_entries(user_query)
    dedupe_summary = load_entity_resolution_summary()

    prompt = f"""Relevant dataset catalog entries:
{catalog_matches}

Entity resolution summary:
duplicate customers found: {dedupe_summary.get('duplicate_customers_found', 'not computed')}
cross-source matches found: {dedupe_summary.get('cross_source_matches_found', 'not computed')}

Question: {user_query}

Answer using only the catalog data above."""

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return response.text


if __name__ == "__main__":
    print(answer_query("Which datasets contain customer PII and have poor data quality?"))
