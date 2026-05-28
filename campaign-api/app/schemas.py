from enum import Enum

from pydantic import BaseModel, Field


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


class CampaignRequest(BaseModel):
    campaign_name: str
    campaign_description: str
    hotel_name: str = "Simon Casino Resort"
    target_audience: str
    theme: CampaignTheme = CampaignTheme.LUXURY_GOLD
    start_date: str
    end_date: str
