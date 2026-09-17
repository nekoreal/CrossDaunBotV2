from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class GalleryPaginateParams(BaseModel):
    categories: Optional[List[str]] = Field(default=None)
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=32, ge=1, le=100)
 
    sort_by: Literal["edit_date", "id"] = Field(default="edit_date")
 
    sort_order: Literal["DESC", "ASC"] = Field(default="DESC")

    @field_validator("categories", mode="before")
    @classmethod
    def parse_categories(cls, v):
        if isinstance(v, str):
            return [cat.strip() for cat in v.split(",") if cat.strip()]
        if isinstance(v, list):
            return [str(cat).strip() for cat in v if str(cat).strip()]
        return v

    # Приводим строки к верхнему регистру перед проверкой sort_order ("desc" -> "DESC")
    @field_validator("sort_order", mode="before")
    @classmethod
    def normalize_sort_order(cls, v):
        if isinstance(v, str):
            return v.upper()
        return v