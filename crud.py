import os
import logging
import httpx
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorCollection
from datetime import datetime
from pymongo import UpdateOne

OFF_API_BASE = "https://world.openfoodfacts.org/api/v0/product"
CARBON_API_URL = "https://api.carboninterface.com/v1/estimates"
CARBON_API_KEY = os.getenv("CARBON_API_KEY")

logger = logging.getLogger("barcode-api")


async def fetch_carbon_footprint(grams: float) -> Optional[float]:
    """
    Given weight in grams, call Carbon Interface to get kg CO2e.
    Logs any non-201 response or request errors.
    """
    payload = {
        "type": "estimate",
        "parameters": {
            "weight_value": grams,
            "weight_unit": "g"
        }
    }
    headers = {
        "Authorization": f"Bearer {CARBON_API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                CARBON_API_URL,
                json=payload,
                headers=headers,
                timeout=10.0
            )
        if resp.status_code != 201:
            logger.warning(f"Carbon API non-201: {resp.status_code} body={resp.text}")
            return None
        data = resp.json().get("data", {}).get("attributes", {})
        return data.get("carbon_kg")
    except httpx.RequestError as e:
        logger.error(f"Carbon API request error: {e}")
        return None
    except ValueError as e:
        logger.error(f"Carbon API JSON parse error: {e}")
        return None


async def fetch_from_off(barcode: str) -> Optional[Dict[str, Any]]:
    """
    Fetch product data from OpenFoodFacts by barcode and enrich with sustainability data.
    """
    url = f"{OFF_API_BASE}/{barcode}.json"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10.0)

    if resp.status_code != 200 or resp.json().get("status") != 1:
        return None

    p = resp.json()["product"]

    # Product name fallback logic
    name = (
        p.get("product_name")
        or p.get("product_name_en")
        or p.get("generic_name")
        or p.get("generic_name_en")
        or p.get("brands")
        or "Unknown Product"
    ).strip()

    # Nutriment helper
    def num_field(key: str) -> Optional[float]:
        for suffix in ("_100g", ""):
            v = p.get("nutriments", {}).get(f"{key}{suffix}")
            if isinstance(v, (int, float)):
                return float(v)
        return None

    # Packaging recyclability check
    pack_str = p.get("packaging", "") or ""
    pack_recyclable = any(
        kw in pack_str.lower()
        for kw in ("recyclable", "recycle", "please recycle")
    )

    # Grams estimate (from serving_size or default to 100g)
    grams: float
    serving = p.get("serving_size")
    if serving:
        try:
            amt, unit = serving.lower().split()
            val = float(amt.replace(",", "."))
            grams = val * (1000 if unit.startswith("kg") else 1)
        except Exception:
            grams = 100.0
    else:
        grams = 100.0

    # Try to get carbon footprint
    carbon_kg = await fetch_carbon_footprint(grams)

    return {
        "barcode": barcode,
        "name": name,
        "brand": p.get("brands", ""),
        "category": p.get("categories", ""),
        "ingredients": [
            i.get("text") for i in p.get("ingredients", []) if i.get("text")
        ],
        "nutriments": {
            "calories": num_field("energy-kcal"),
            "fat":      num_field("fat"),
            "sugar":    num_field("sugars"),
            "sodium":   num_field("sodium"),
        },
        "allergens": p.get("allergens_hierarchy", []),
        "eco": {
            "eco_score":            p.get("ecoscore_score"),
            "carbon_footprint":     carbon_kg,
            "packaging_recyclable": pack_recyclable,
        },
        "fetched_at": datetime.utcnow()
    }


async def upsert_product(collection: AsyncIOMotorCollection, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upserts a single product document into the MongoDB collection.
    """
    await collection.update_one(
        {"barcode": data["barcode"]},
        {"$set": data},
        upsert=True
    )
    doc = await collection.find_one({"barcode": data["barcode"]})
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])  # Serialize ObjectId
    return doc


async def bulk_upsert_products(collection: AsyncIOMotorCollection, docs: List[Dict[str, Any]]):
    """
    Performs a bulk upsert of multiple products.
    """
    operations = [
        UpdateOne({"barcode": doc["barcode"]}, {"$set": doc}, upsert=True)
        for doc in docs
    ]
    if operations:
        await collection.bulk_write(operations)


async def get_product(collection: AsyncIOMotorCollection, barcode: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a product by barcode.
    """
    doc = await collection.find_one({"barcode": barcode})
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])  # Serialize ObjectId
    return doc


async def search_products(collection: AsyncIOMotorCollection, query: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Search products using a MongoDB query.
    """
    cursor = collection.find(query)
    results = await cursor.to_list(length=100)
    for doc in results:
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])  # Serialize ObjectId
    return results

