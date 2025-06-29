# database.py

import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "products_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "products")

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]

async def ensure_indexes():
    # TTL index on fetched_at: documents expire 24h after fetched_at
    await collection.create_index(
        "fetched_at",
        expireAfterSeconds=86400
    )
