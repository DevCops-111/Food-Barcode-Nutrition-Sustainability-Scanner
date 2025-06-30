from typing import List, Optional, Union, Any
from bson import ObjectId
from pydantic import BaseModel, Field
from pydantic_core import core_schema
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue


# === Custom ObjectId Support for Pydantic v2 ===
class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema()
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return {"type": "string"}

    @classmethod
    def validate(cls, v: Any) -> "PyObjectId":
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError("Invalid ObjectId")


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
