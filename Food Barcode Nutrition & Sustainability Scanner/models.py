from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class Nutriments(BaseModel):
    calories: Optional[float]
    fat: Optional[float]
    sugar: Optional[float]
    sodium: Optional[float]

class EcoInfo(BaseModel):
    eco_score: Optional[int]
    carbon_footprint: Optional[float]
    packaging_recyclable: bool

class Product(BaseModel):
    barcode: str
    name: str
    brand: str
    category: str
    ingredients: List[str]
    nutriments: Nutriments
    allergens: List[str]
    eco: EcoInfo
    _id: Optional[str] = Field(default=None, alias="_id")  # ObjectId as string

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            # ObjectId will be handled before this now
        }

class BarcodeIn(BaseModel):
    barcode: str
