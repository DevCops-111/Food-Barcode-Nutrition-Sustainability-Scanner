import logging
import uuid
import asyncio

from fastapi import FastAPI, Request, HTTPException, status, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Union

from database import collection, ensure_indexes
import crud
from schemas import (
    ProductOut,
    Nutriments,
    EcoScore,
    ErrorOut,
    BatchMetadata,
    BatchResponse,
)

# ─── configure logger ──────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("barcode-api")

app = FastAPI(
    title="Barcode Nutrition & Eco API",
    version="1.4",
    description="Now with per-item errors, throttling, TTL, bulk upserts, and batch metadata!"
)

# ─── ensure TTL index on startup ───────────
@app.on_event("startup")
async def on_startup():
    await ensure_indexes()
    logger.info("TTL index on 'fetched_at' ensured")

# ─── request logging middleware ────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    req_id = str(uuid.uuid4())[:8]
    logger.info(f"[{req_id}] ▶ START {request.method} {request.url.path}")
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(f"[{req_id}] ✖ UNHANDLED ERROR")
        raise
    logger.info(f"[{req_id}] ✔ COMPLETE {response.status_code}")
    return response

# ─── global exception handler ──────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception during request: {exc}", exc_info=True)
    return PlainTextResponse("Internal Server Error", status_code=500)

# ─── input models ──────────────────────────
class BarcodeInput(BaseModel):
    barcode: str

class BarcodesInput(BaseModel):
    barcodes: List[str]

# ─── single product endpoint ──────────────
@app.post(
    "/product",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    summary="Fetch live from OFF and upsert single product"
)
async def create_or_update_product(barcode_in: BarcodeInput):
    try:
        off_data = await crud.fetch_from_off(barcode_in.barcode)
        if not off_data:
            raise HTTPException(
                status_code=404,
                detail="Product not found in OpenFoodFacts"
            )
        await crud.bulk_upsert_products(collection, [off_data])
        doc = await crud.get_product(collection, barcode_in.barcode)
        return doc

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error in create_or_update_product")
        raise HTTPException(
            status_code=500,
            detail="Failed to create or update product"
        )

# ─── batch lookup with metadata ────────────
@app.post(
    "/products/batch",
    response_model=BatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch lookup with metadata, throttling, and error reporting"
)
async def batch_lookup(batch: BarcodesInput):
    requested = len(batch.barcodes)
    fetched = 0
    cached = 0

    semaphore = asyncio.Semaphore(5)
    new_products: List[Dict[str, Any]] = []
    results: List[Union[Dict[str, Any], Dict[str, str]]] = []

    async def process_one(code: str):
        nonlocal fetched, cached
        # 1. Try cache
        doc = await crud.get_product(collection, code)
        if doc:
            cached += 1
            results.append(doc)
            return

        # 2. Throttled fetch
        async with semaphore:
            off_data = await crud.fetch_from_off(code)

        if not off_data:
            results.append({"barcode": code, "error": "Not found in OpenFoodFacts"})
            return

        fetched += 1
        new_products.append(off_data)
        results.append({"barcode": code, "_placeholder": True})

    # Run all lookups
    await asyncio.gather(*(process_one(c) for c in batch.barcodes))

    # Bulk upsert new products
    if new_products:
        await crud.bulk_upsert_products(collection, new_products)
        # Replace placeholders with real docs
        for idx, item in enumerate(results):
            if item.get("_placeholder"):
                code = item["barcode"]
                doc = await crud.get_product(collection, code)
                results[idx] = doc

    metadata = BatchMetadata(requested=requested, fetched=fetched, cached=cached)
    return BatchResponse(metadata=metadata, results=results)

# ─── GET: other endpoints unchanged ───────

@app.get("/product/{barcode}", response_model=ProductOut)
async def get_product(barcode: str):
    doc = await crud.get_product(collection, barcode)
    if not doc:
        raise HTTPException(404, "Product not found")
    return doc

@app.get("/product/{barcode}/nutrients", response_model=Nutriments)
async def get_nutrients(barcode: str):
    doc = await crud.get_product(collection, barcode)
    if not doc or not doc.get("nutriments"):
        raise HTTPException(404, "Nutrition data not found")
    return doc["nutriments"]

@app.get("/product/{barcode}/allergens")
async def get_allergens(barcode: str):
    doc = await crud.get_product(collection, barcode)
    if not doc or not doc.get("allergens"):
        raise HTTPException(404, "Allergen data not found")
    return {"allergens": doc["allergens"]}

@app.get("/product/{barcode}/eco", response_model=EcoScore)
async def get_eco(barcode: str):
    doc = await crud.get_product(collection, barcode)
    if not doc or not doc.get("eco"):
        raise HTTPException(404, "Eco data not found")
    return doc["eco"]

@app.get("/search", response_model=List[ProductOut])
async def search(q: str = Query(..., min_length=2)):
    return await crud.search_products(collection, q)

@app.get("/", include_in_schema=False)
async def read_root():
    return {"message": "Welcome to the Food Barcode Nutrition & Sustainability API"}
