import os
import random
import pandas as pd
from faker import Faker
from sqlalchemy import create_engine
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

fake = Faker()
random.seed(42)
Faker.seed(42)

PG_URL = os.environ.get("DATABASE_URL", "postgresql://dataplatform:dataplatform@localhost:5432/crm_db")
MONGO_URL = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
DATA_DIR = os.path.dirname(os.path.abspath(__file__))

N_CUSTOMERS = 500
N_DUPLICATES = 60
N_ORDERS = 2000
N_TICKETS = 300
N_LEADS = 400


def make_customers():
    customers = []
    for i in range(N_CUSTOMERS):
        customers.append({
            "customer_id": i + 1,
            "full_name": fake.name(),
            "email": fake.email(),
            "phone": fake.phone_number(),
            "ssn_like_id": fake.ssn(),
            "signup_date": fake.date_between(start_date="-3y", end_date="today"),
            "region": random.choice(["APAC", "EMEA", "NA", "LATAM"]),
        })

    base = random.sample(customers, N_DUPLICATES)
    for i, c in enumerate(base):
        dup = c.copy()
        dup["customer_id"] = N_CUSTOMERS + i + 1
        dup["full_name"] = c["full_name"].replace(" ", "  ") if i % 2 == 0 else c["full_name"].upper()
        dup["email"] = c["email"].replace("@", "+dup@") if i % 3 == 0 else c["email"]
        customers.append(dup)

    df = pd.DataFrame(customers)
    null_idx = df.sample(frac=0.08).index
    df.loc[null_idx, "phone"] = None
    return df


def make_orders(customers_df):
    orders = []
    ids = customers_df["customer_id"].tolist()
    for i in range(N_ORDERS):
        orders.append({
            "order_id": i + 1,
            "customer_id": random.choice(ids),
            "amount": round(random.uniform(10, 2000), 2),
            "order_date": fake.date_between(start_date="-2y", end_date="today"),
            "status": random.choice(["completed", "refunded", "pending", "cancelled"]),
        })
    return pd.DataFrame(orders)


def make_support_tickets():
    tickets = []
    for i in range(N_TICKETS):
        tickets.append({
            "ticket_id": i + 1,
            "customer_email": fake.email(),
            "subject": fake.sentence(nb_words=6),
            "body": fake.paragraph(nb_sentences=3),
            "credit_card_mentioned": fake.credit_card_number() if random.random() < 0.05 else None,
            "priority": random.choice(["low", "medium", "high"]),
        })
    return tickets


def make_leads_csv():
    leads = []
    for i in range(N_LEADS):
        leads.append({
            "lead_id": i + 1,
            "name": fake.name(),
            "email": fake.email(),
            "company": fake.company(),
            "source": random.choice(["webinar", "ads", "referral", "organic"]),
        })
    df = pd.DataFrame(leads)
    df.to_csv(os.path.join(DATA_DIR, "marketing_leads.csv"), index=False)


def main():
    customers_df = make_customers()
    orders_df = make_orders(customers_df)

    pg_engine = create_engine(PG_URL)
    customers_df.to_sql("customers", pg_engine, if_exists="replace", index=False)
    orders_df.to_sql("orders", pg_engine, if_exists="replace", index=False)
    print(f"Loaded {len(customers_df)} customers, {len(orders_df)} orders into Postgres")

    mongo = MongoClient(MONGO_URL)
    db = mongo["support_db"]
    db["support_tickets"].delete_many({})
    db["support_tickets"].insert_many(make_support_tickets())
    print(f"Loaded {N_TICKETS} support tickets into Mongo")

    make_leads_csv()
    print(f"Generated marketing_leads.csv ({N_LEADS} rows)")


if __name__ == "__main__":
    main()
