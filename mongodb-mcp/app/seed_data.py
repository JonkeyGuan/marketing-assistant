import os
import time

from app.vertical_config import seed_data

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DATABASE = "casino_crm"
CUSTOMERS = []
PROSPECTS = []


def init():
    global MONGODB_DATABASE
    # Retry to tolerate ztunnel/ambient mesh network readiness delay
    for attempt in range(5):
        try:
            _seed = seed_data()
            break
        except Exception:
            if attempt < 4:
                print(f"[Seed] Config fetch attempt {attempt + 1}/5 failed, retrying in 2s...")
                time.sleep(2)
            else:
                raise
    MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", _seed.get("database_name", "casino_crm"))
    CUSTOMERS[:] = _seed.get("customers", [])
    PROSPECTS[:] = _seed.get("prospects", [])


def seed():
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure

    print(f"[Seed] Connecting to {MONGODB_URI}...")
    for attempt in range(10):
        try:
            client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            client.server_info()
            break
        except ConnectionFailure:
            print(f"[Seed] Waiting for MongoDB... (attempt {attempt + 1}/10)")
            time.sleep(3)
    else:
        print("[Seed] Could not connect to MongoDB after 10 attempts")
        return

    db = client[MONGODB_DATABASE]

    if db.customers.count_documents({}) > 0:
        print(f"[Seed] Data already exists ({db.customers.count_documents({})} customers, {db.prospects.count_documents({})} prospects). Skipping.")
        client.close()
        return

    if CUSTOMERS:
        db.customers.insert_many(CUSTOMERS)
        print(f"[Seed] Inserted {len(CUSTOMERS)} customers into {MONGODB_DATABASE}.customers")

    if PROSPECTS:
        db.prospects.insert_many(PROSPECTS)
        print(f"[Seed] Inserted {len(PROSPECTS)} prospects into {MONGODB_DATABASE}.prospects")

    db.customers.create_index("tier")
    db.customers.create_index("total_spend")
    db.customers.create_index("customer_id", unique=True)
    db.prospects.create_index("customer_id", unique=True)
    print("[Seed] Indexes created. Done!")
    client.close()


if __name__ == "__main__":
    init()
    seed()
