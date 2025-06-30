from pydantic import BaseModel, Field
from typing import List, Optional, Union, Any
from bson import ObjectId


# === Helper for serializing ObjectId ===
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: Any):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(str(v))

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


# === Submodels ===

class Nutriments(BaseModel):
    calories: Optional[float]
    fat: Optional[float]
    sugar: Optional[float]
    sodium: Optional[float]


class EcoScore(BaseModel):
    eco_score: Optional[int]
    carbon_footprint: Optional[float]
    packaging_recyclable: Optional[bool]


# === Main Product Model ===

class ProductOut(BaseModel):
    barcode: str
    name: str
    brand: Optional[str]
    category: Optional[str]
    ingredients: Optional[List[str]]

    # Correctly handle MongoDB ObjectId with alias
    id: PyObjectId = Field(..., alias="_id")

    nutriments: Optional[Nutriments]
    allergens: Optional[List[str]]
    eco: Optional[EcoScore]

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str
        }


# === Error Wrapper Model ===

class ErrorOut(BaseModel):
    barcode: str
    error: str


# === Batch Metadata and Result Response ===

class BatchMetadata(BaseModel):
    requested: int
    fetched: int
    cached: int


class BatchResponse(BaseModel):
    metadata: BatchMetadata
    results: List[Union[ProductOut, ErrorOut]]

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str
        }
