from typing import List, Optional
from pydantic import BaseModel, Field


class CustomerProfile(BaseModel):
    customer_id: str
    name: str
    name_en: Optional[str] = None
    email: str
    tier: str
    preferred_language: str = "en"
    interests: List[str] = Field(default_factory=list)
    total_spend: Optional[int] = None
    last_visit: Optional[str] = None
    source: Optional[str] = None


class GetTargetCustomersOutput(BaseModel):
    customers: List[CustomerProfile]
    count: int
    recipient_type: str
    status: str = "success"
    error: Optional[str] = None
