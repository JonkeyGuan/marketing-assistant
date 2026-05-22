from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class CampaignTheme(str, Enum):
    LUXURY_GOLD = "luxury_gold"
    FESTIVE_RED = "festive_red"
    MODERN_BLACK = "modern_black"
    CLASSIC_EMERALD = "classic_emerald"


CAMPAIGN_THEMES = {
    "luxury_gold": {
        "name": "Luxury Gold",
        "description": "Timeless warmth, deep midnight slate with classic gold accents",
        "primary_color": "#D4AF37",
        "secondary_color": "#0F172A",
        "accent_color": "#FDE047",
        "background": "#0F172A",
        "text_color": "#F8FAFC",
        "button_color": "#D4AF37",
        "button_text": "#0F172A"
    },
    "festive_red": {
        "name": "Festive Red",
        "description": "Professional yet celebratory, deep maroon with crimson and gold",
        "primary_color": "#C41E3A",
        "secondary_color": "#450A0A",
        "accent_color": "#B8860B",
        "background": "#450A0A",
        "text_color": "#FFFFFF",
        "button_color": "#C41E3A",
        "button_text": "#FFFFFF"
    },
    "modern_black": {
        "name": "Modern Minimal",
        "description": "Architectural, crisp, ultra-clean with maximum whitespace",
        "primary_color": "#0F172A",
        "secondary_color": "#F8FAFC",
        "accent_color": "#334155",
        "background": "#FFFFFF",
        "text_color": "#0F172A",
        "button_color": "#0F172A",
        "button_text": "#FFFFFF"
    },
    "classic_emerald": {
        "name": "Classic Emerald",
        "description": "Deep emerald with amber gold, timeless prestige",
        "primary_color": "#F59E0B",
        "secondary_color": "#064E3B",
        "accent_color": "#D1D5DB",
        "background": "#064E3B",
        "text_color": "#F0FDF4",
        "button_color": "#F59E0B",
        "button_text": "#064E3B"
    }
}


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    PREVIEW_READY = "preview_ready"
    PREPARING_EMAIL = "preparing_email"
    EMAIL_READY = "email_ready"
    APPROVED = "approved"
    DEPLOYING = "deploying"
    LIVE = "live"
    FAILED = "failed"


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


class CampaignRequest(BaseModel):
    campaign_name: str
    campaign_description: str
    hotel_name: str = "Simon Casino Resort"
    target_audience: str
    theme: CampaignTheme = CampaignTheme.LUXURY_GOLD
    start_date: str
    end_date: str


class CampaignData(BaseModel):
    id: str
    campaign_name: str
    campaign_description: str
    hotel_name: str
    target_audience: str
    theme: str
    start_date: str
    end_date: str
    status: CampaignStatus = CampaignStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.utcnow)

    landing_page_html: Optional[str] = None
    hero_image_url: Optional[str] = None
    preview_url: Optional[str] = None
    production_url: Optional[str] = None

    email_subject_en: Optional[str] = None
    email_body_en: Optional[str] = None
    email_subject_zh: Optional[str] = None
    email_body_zh: Optional[str] = None

    customer_list: List[CustomerProfile] = Field(default_factory=list)
    customer_count: int = 0

    error_message: Optional[str] = None


class AgentEvent(BaseModel):
    campaign_id: str
    event_type: str
    agent: Optional[str] = None
    task: Optional[str] = None
    status: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
