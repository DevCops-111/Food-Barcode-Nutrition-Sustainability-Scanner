from pydantic import BaseModel, Field
from typing import List, Optional, Union

class Nutriments(BaseModel):
    calories: Optional[float]
    fat: Optional[float]
    sugar: Optional[float]
    sodium: Optional[float]

class EcoScore(BaseModel):
    eco_score: Optional[int]
    carbon_footprint: Optional[float]
    packaging_recyclable: Optional[bool]

class ProductOut(BaseModel):
    barcode: str
    name: str
    brand: Optional[str]
    category: Optional[str]
    ingredients: Optional[List[str]]
    # Rename the field to "id", but alias from "_id" in the DB document:
    id: str = Field(..., alias="_id")
    nutriments: Optional[Nutriments]
    allergens: Optional[List[str]]
    eco: Optional[EcoScore]

    model_config = {
        "populate_by_name": True,  # allows you to read/write "id" by alias "_id"
    }

class ErrorOut(BaseModel):
    barcode: str
    error: str

class BatchMetadata(BaseModel):
    requested: int
    fetched: int
    cached: int

class BatchResponse(BaseModel):
    metadata: BatchMetadata
    results: List[Union[ProductOut, ErrorOut]]

    model_config = {
        "populate_by_name": True,
    }
