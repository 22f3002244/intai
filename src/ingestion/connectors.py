import os
import pandas as pd
from sqlalchemy import create_engine
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

PG_URL = os.environ.get("DATABASE_URL", "postgresql://dataplatform:dataplatform@localhost:5434/crm_db")
MONGO_URL = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")


def list_sources():
    return [
        {"name": "customers", "type": "postgres", "table": "customers"},
        {"name": "orders", "type": "postgres", "table": "orders"},
        {"name": "support_tickets", "type": "mongo", "collection": "support_tickets"},
        {"name": "marketing_leads", "type": "csv", "path": os.path.join(DATA_DIR, "marketing_leads.csv")},
    ]


def read_postgres_table(table_name):
    engine = create_engine(PG_URL)
    return pd.read_sql_table(table_name, engine)


def read_mongo_collection(collection_name):
    client = MongoClient(MONGO_URL)
    db = client["support_db"]
    docs = list(db[collection_name].find({}, {"_id": 0}))
    return pd.DataFrame(docs)


def read_csv_source(path):
    return pd.read_csv(path)


def load_dataset(source):
    if source["type"] == "postgres":
        return read_postgres_table(source["table"])
    if source["type"] == "mongo":
        return read_mongo_collection(source["collection"])
    if source["type"] == "csv":
        return read_csv_source(source["path"])
    raise ValueError(f"Unknown source type: {source['type']}")


def load_all():
    return {s["name"]: load_dataset(s) for s in list_sources()}


if __name__ == "__main__":
    datasets = load_all()
    for name, df in datasets.items():
        print(f"{name}: {df.shape[0]} rows, {df.shape[1]} columns")
