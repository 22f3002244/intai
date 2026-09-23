# Data Intelligence Platform

AI-powered data management platform for profiling, entity resolution, governance, and natural-language querying.

## What it does

- Pulls data from Postgres, MongoDB, and CSV files
- Profiles each dataset (row counts, null rates, outliers, duplicate rows, column types etc.)
- Scores data quality and flags columns with issues (null rate, ID cardinality, outlier rate)
- Detects PII columns like emails, phone numbers, and SSNs using spaCy and regex — stores confidence scores
- Finds duplicate customer records across sources using fuzzy matching (vectorized with `rapidfuzz.cdist`)
- Stores dataset descriptions as embeddings in ChromaDB with content-hash staleness detection
- Uses Gemini to answer natural language questions about the data
- Has a human-in-the-loop approval workflow before any corrective action runs (full reject/execute/verify cycle)
- Pending actions are stored in Redis — survives restarts and works across workers
- Exposes everything through a FastAPI REST API with CORS support

## Stack

Python, FastAPI, PostgreSQL, MongoDB, ChromaDB, Redis, sentence-transformers, spaCy, RapidFuzz, Google Gemini API, Docker

## Setup

```bash
# Start the databases
docker-compose up -d

# Install the project as an editable package (fixes all import paths)
pip install -e .

# Install runtime dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Copy the example env file and fill in your Gemini API key
cp .env.example .env   # then edit .env and set GEMINI_API_KEY
```

## Running the pipeline

```bash
python data/generate_synthetic_data.py   # creates fake customer/order/ticket data
python src/profiling/profiler.py         # profiles all datasets (now includes outliers & dup rows)
python src/quality/quality_engine.py
python src/metadata/pii_detection.py
python src/entity_resolution/dedupe.py
python src/catalog/build_catalog_index.py          # skips re-embedding if data hasn't changed
python src/catalog/build_catalog_index.py --force  # force rebuild
python src/agent/query_agent.py          # optional: test the NL agent
```

## Start the API

```bash
uvicorn src.api.main:app --reload --port 8081
```

Then go to http://localhost:8081/docs to try the endpoints.

## API endpoints

| Endpoint | Description |
|---|---|
| `GET  /catalog/profiles` | Dataset schema and stats |
| `GET  /catalog/quality` | Quality scores per dataset |
| `GET  /catalog/pii` | Detected PII columns (with confidence) |
| `GET  /entity-resolution/duplicates` | Duplicate records (cached in Redis) |
| `DELETE /entity-resolution/cache` | Invalidate the entity-resolution cache |
| `POST /query` | Ask a question in plain English |
| `POST /actions/{id}/propose` | Propose a corrective action |
| `GET  /actions/{id}` | Get current state of an action |
| `POST /actions/approve` | Approve a pending action |
| `POST /actions/reject` | Reject a pending action |
| `POST /actions/{id}/execute` | Execute an approved action |
| `POST /actions/{id}/verify` | Verify an executed action |

## Running tests

```bash
pytest
```

## Note

The data is all synthetic and generated locally using Faker — no external datasets needed. Duplicates, missing values, and inconsistent formats are intentionally included to exercise the quality and deduplication logic.
