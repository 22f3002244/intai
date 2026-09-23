# Data Intelligence Platform

AI-powered data management platform for profiling, entity resolution, governance, and natural-language querying.

## What it does

- Pulls data from Postgres, MongoDB, and CSV files
- Profiles each dataset (row counts, null rates, column types etc.)
- Scores data quality and flags columns with issues
- Detects PII columns like emails, phone numbers, and SSNs using spaCy and regex
- Finds duplicate customer records across sources using fuzzy matching
- Stores dataset descriptions as embeddings in ChromaDB
- Uses Gemini to answer natural language questions about the data
- Has a simple approval workflow before any corrective action runs
- Exposes everything through a FastAPI REST API

## Stack

Python, FastAPI, PostgreSQL, MongoDB, ChromaDB, sentence-transformers, spaCy, RapidFuzz, Google Gemini API, Docker

## Setup

```bash
# Start the databases
docker-compose up -d

# Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Copy the example env file and fill in your Gemini API key
cp .env.example .env
# Then edit .env and set GEMINI_API_KEY
```

## Running the pipeline

```bash
python data/generate_synthetic_data.py   # creates fake customer/order/ticket data
python src/profiling/profiler.py
python src/quality/quality_engine.py
python src/metadata/pii_detection.py
python src/entity_resolution/dedupe.py
python src/catalog/build_catalog_index.py
python src/agent/query_agent.py          # optional: test the NL agent
```

## Start the API

```bash
uvicorn src.api.main:app --reload --port 8000
```

Then go to http://localhost:8000/docs to try the endpoints.

## API endpoints

| Endpoint | Description |
|---|---|
| `GET /catalog/profiles` | Dataset schema and stats |
| `GET /catalog/quality` | Quality scores per dataset |
| `GET /catalog/pii` | Detected PII columns |
| `GET /entity-resolution/duplicates` | Duplicate records found |
| `POST /query` | Ask a question in plain English |
| `POST /actions/{id}/propose` | Propose a corrective action |
| `POST /actions/approve` | Approve a pending action |

## Note

The data is all synthetic and generated locally using Faker — no external datasets needed. I intentionally added duplicates, missing values, and inconsistent formats to make the quality checks and deduplication actually useful.
