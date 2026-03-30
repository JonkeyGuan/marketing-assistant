"""
Shared state definition for the LangGraph workflow.
"""
from typing import TypedDict, Annotated, Optional, List
import operator


class CampaignState(TypedDict):
    """State that flows through the multi-agent workflow."""
    
    # Conversation history
    messages: Annotated[List[dict], operator.add]
    
    # Campaign details from user input
    campaign_name: str
    campaign_description: str
    hotel_name: str
    target_audience: str
    start_date: str
    end_date: str
    
    # Theme selection
    selected_theme: str
    theme_colors: dict
    
    # Generated content
    generated_html: str
    generated_css: str
    generated_js: str
    
    # Deployment info
    container_image: str
    deployment_name: str
    preview_url: str
    preview_qr_code: str
    production_url: str
    
    # Email content
    email_subject_en: str
    email_body_en: str
    email_subject_zh: str
    email_body_zh: str
    
    # Customer data
    customer_list: List[dict]
    
    # Workflow control
    current_step: str
    awaiting_approval: bool
    user_decision: str  # "edit" or "approve"
    error_message: str
    
    # Metadata
    campaign_id: str
    created_at: str


# Available themes
CAMPAIGN_THEMES = {
    "luxury_gold": {
        "name": "Luxury Gold",
        "description": "Elegant, minimalist, premium feel for VIP exclusive offers",
        "colors": {
            "primary": "#D4AF37",
            "secondary": "#1A1A1A",
            "accent": "#FFFFFF",
            "background": "#0D0D0D",
            "text": "#FFFFFF"
        }
    },
    "festive_red": {
        "name": "Festive Red",
        "description": "Celebratory Chinese New Year theme for holiday promotions",
        "colors": {
            "primary": "#C41E3A",
            "secondary": "#D4AF37",
            "accent": "#FFFFFF",
            "background": "#1A0A0A",
            "text": "#FFFFFF"
        }
    },
    "modern_black": {
        "name": "Modern Black",
        "description": "Sleek, contemporary, tech-forward for new member promotions",
        "colors": {
            "primary": "#1A1A1A",
            "secondary": "#C0C0C0",
            "accent": "#00D4FF",
            "background": "#0A0A0A",
            "text": "#FFFFFF"
        }
    },
    "classic_casino": {
        "name": "Classic Casino",
        "description": "Traditional casino aesthetic for gaming promotions",
        "colors": {
            "primary": "#228B22",
            "secondary": "#D4AF37",
            "accent": "#8B0000",
            "background": "#0D1A0D",
            "text": "#FFFFFF"
        }
    }
}


def create_initial_state(
    campaign_name: str = "",
    campaign_description: str = "",
    hotel_name: str = "Grand Luxe Hotel & Casino",
    target_audience: str = "VIP members",
    start_date: str = "",
    end_date: str = ""
) -> CampaignState:
    """Create initial state for a new campaign workflow."""
    import uuid
    from datetime import datetime
    
    return CampaignState(
        messages=[],
        campaign_name=campaign_name,
        campaign_description=campaign_description,
        hotel_name=hotel_name,
        target_audience=target_audience,
        start_date=start_date,
        end_date=end_date,
        selected_theme="",
        theme_colors={},
        generated_html="",
        generated_css="",
        generated_js="",
        container_image="",
        deployment_name="",
        preview_url="",
        preview_qr_code="",
        production_url="",
        email_subject_en="",
        email_body_en="",
        email_subject_zh="",
        email_body_zh="",
        customer_list=[],
        current_step="gather_requirements",
        awaiting_approval=False,
        user_decision="",
        error_message="",
        campaign_id=f"campaign-{uuid.uuid4().hex[:8]}",
        created_at=datetime.now().isoformat()
    )
