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


class GenerateEmailInput(BaseModel):
    campaign_name: str
    campaign_description: str
    hotel_name: str
    campaign_url: str
    target_audience: str
    start_date: str
    end_date: str


class GenerateEmailOutput(BaseModel):
    email_subject_en: str
    email_body_en: str
    email_subject_zh: str
    email_body_zh: str
    status: str = "success"
    error: Optional[str] = None


class DeployPreviewInput(BaseModel):
    campaign_id: str
    html_content: str
    namespace: str = "marketing-assistant-dev"


class DeployPreviewOutput(BaseModel):
    preview_url: str
    status: str = "success"
    error: Optional[str] = None


class DeployProductionInput(BaseModel):
    campaign_id: str
    html_content: str
    namespace: str = "marketing-assistant-prod"


class DeployProductionOutput(BaseModel):
    production_url: str
    status: str = "success"
    error: Optional[str] = None


class SendEmailsInput(BaseModel):
    campaign_id: str
    customers: List[CustomerProfile]
    email_subject_en: str
    email_body_en: str
    email_subject_zh: str
    email_body_zh: str


class SendEmailsOutput(BaseModel):
    sent_count: int
    status: str = "success"
    error: Optional[str] = None
