import sys
import os
import itertools
from rapidfuzz import fuzz

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from src.ingestion.connectors import load_all

NAME_MATCH_THRESHOLD = 85
EMAIL_MATCH_THRESHOLD = 90


def normalize(value):
    return str(value).strip().lower().replace("  ", " ")


def find_duplicate_customers(customers_df):
    records = customers_df[["customer_id", "full_name", "email"]].to_dict("records")
    matches = []

    for a, b in itertools.combinations(records, 2):
        name_score = fuzz.token_sort_ratio(normalize(a["full_name"]), normalize(b["full_name"]))
        email_a = normalize(a["email"]).split("+dup")[0]
        email_b = normalize(b["email"]).split("+dup")[0]
        email_score = fuzz.ratio(email_a, email_b)

        if name_score >= NAME_MATCH_THRESHOLD or email_score >= EMAIL_MATCH_THRESHOLD:
            matches.append({
                "customer_id_a": a["customer_id"],
                "customer_id_b": b["customer_id"],
                "name_similarity": name_score,
                "email_similarity": email_score,
            })

    return matches


def find_cross_source_matches(customers_df, leads_df):
    matches = []
    for _, customer in customers_df.iterrows():
        for _, lead in leads_df.iterrows():
            score = fuzz.ratio(normalize(customer["email"]), normalize(lead["email"]))
            if score >= EMAIL_MATCH_THRESHOLD:
                matches.append({
                    "customer_id": customer["customer_id"],
                    "lead_id": lead["lead_id"],
                    "email_similarity": score,
                })
    return matches


def run_entity_resolution():
    datasets = load_all()
    customers_df = datasets["customers"]
    leads_df = datasets["marketing_leads"]

    duplicate_customers = find_duplicate_customers(customers_df)
    cross_source = find_cross_source_matches(customers_df, leads_df)

    return {
        "duplicate_customers_found": len(duplicate_customers),
        "duplicates": duplicate_customers,
        "cross_source_matches_found": len(cross_source),
        "cross_source_matches": cross_source,
    }


if __name__ == "__main__":
    result = run_entity_resolution()
    print(f"Found {result['duplicate_customers_found']} likely duplicate customer records")
    print(f"Found {result['cross_source_matches_found']} cross-source (customer <-> lead) matches")
