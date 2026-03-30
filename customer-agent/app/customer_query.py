"""
Core skill: Query customer profiles from MongoDB or mock data.
"""
import logging
from typing import Dict, List, Optional

from app.settings import settings

logger = logging.getLogger(__name__)

# Mock prospect data for "new members" campaigns
MOCK_PROSPECTS = [
    {
        "customer_id": "PROSPECT-001",
        "name": "赵雪",
        "name_en": "Xue Zhao",
        "email": "xue.zhao@example.com",
        "tier": "prospect",
        "preferred_language": "zh-CN",
        "interests": ["luxury travel", "fine dining"],
        "source": "hotel_inquiry",
    },
    {
        "customer_id": "PROSPECT-002",
        "name": "David Lee",
        "name_en": "David Lee",
        "email": "david.lee@example.com",
        "tier": "prospect",
        "preferred_language": "en",
        "interests": ["gaming", "entertainment"],
        "source": "website_signup",
    },
    {
        "customer_id": "PROSPECT-003",
        "name": "林美玲",
        "name_en": "Meiling Lin",
        "email": "meiling.lin@example.com",
        "tier": "prospect",
        "preferred_language": "zh-CN",
        "interests": ["spa", "shopping"],
        "source": "partner_referral",
    },
    {
        "customer_id": "PROSPECT-004",
        "name": "James Chen",
        "name_en": "James Chen",
        "email": "james.chen@example.com",
        "tier": "prospect",
        "preferred_language": "en",
        "interests": ["poker", "golf"],
        "source": "event_registration",
    },
    {
        "customer_id": "PROSPECT-005",
        "name": "周婷",
        "name_en": "Ting Zhou",
        "email": "ting.zhou@example.com",
        "tier": "prospect",
        "preferred_language": "zh-CN",
        "interests": ["luxury brands", "fine dining"],
        "source": "social_media",
    },
]

# Mock customer data (used when MongoDB is not available)
MOCK_CUSTOMERS = [
    {
        "customer_id": "VIP-001",
        "name": "张伟",
        "name_en": "Wei Zhang",
        "email": "wei.zhang@example.com",
        "tier": "platinum",
        "preferred_language": "zh-CN",
        "interests": ["baccarat", "fine dining", "spa"],
        "total_spend": 500000,
        "last_visit": "2026-03-15",
    },
    {
        "customer_id": "VIP-002",
        "name": "李明",
        "name_en": "Ming Li",
        "email": "ming.li@example.com",
        "tier": "platinum",
        "preferred_language": "zh-CN",
        "interests": ["blackjack", "golf", "wine"],
        "total_spend": 750000,
        "last_visit": "2026-03-20",
    },
    {
        "customer_id": "VIP-003",
        "name": "王芳",
        "name_en": "Fang Wang",
        "email": "fang.wang@example.com",
        "tier": "gold",
        "preferred_language": "zh-CN",
        "interests": ["slots", "shopping", "spa"],
        "total_spend": 250000,
        "last_visit": "2026-03-10",
    },
    {
        "customer_id": "VIP-004",
        "name": "John Smith",
        "name_en": "John Smith",
        "email": "john.smith@example.com",
        "tier": "platinum",
        "preferred_language": "en",
        "interests": ["poker", "golf", "fine dining"],
        "total_spend": 600000,
        "last_visit": "2026-03-18",
    },
    {
        "customer_id": "VIP-005",
        "name": "陈静",
        "name_en": "Jing Chen",
        "email": "jing.chen@example.com",
        "tier": "gold",
        "preferred_language": "zh-CN",
        "interests": ["baccarat", "spa", "shopping"],
        "total_spend": 300000,
        "last_visit": "2026-03-22",
    },
    {
        "customer_id": "VIP-006",
        "name": "Michael Wong",
        "name_en": "Michael Wong",
        "email": "michael.wong@example.com",
        "tier": "platinum",
        "preferred_language": "en",
        "interests": ["blackjack", "fine dining", "concerts"],
        "total_spend": 450000,
        "last_visit": "2026-03-19",
    },
    {
        "customer_id": "VIP-007",
        "name": "刘洋",
        "name_en": "Yang Liu",
        "email": "yang.liu@example.com",
        "tier": "diamond",
        "preferred_language": "zh-CN",
        "interests": ["baccarat", "private gaming", "yacht"],
        "total_spend": 2000000,
        "last_visit": "2026-03-25",
    },
    {
        "customer_id": "VIP-008",
        "name": "Sarah Johnson",
        "name_en": "Sarah Johnson",
        "email": "sarah.johnson@example.com",
        "tier": "gold",
        "preferred_language": "en",
        "interests": ["slots", "spa", "shows"],
        "total_spend": 180000,
        "last_visit": "2026-03-12",
    },
]


def _get_mongodb_client():
    """Get MongoDB client connection."""
    try:
        from pymongo import MongoClient

        client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)
        client.server_info()
        return client
    except Exception as e:
        logger.warning("MongoDB connection failed: %s", e)
        return None


def _filter_mock_customers(
    tier: Optional[str] = None,
    min_spend: Optional[int] = None,
    interests: Optional[List[str]] = None,
    limit: int = 50,
) -> List[Dict]:
    """Filter mock customers based on criteria."""
    filtered = MOCK_CUSTOMERS.copy()

    if tier:
        filtered = [c for c in filtered if c["tier"] == tier]
    if min_spend:
        filtered = [c for c in filtered if c["total_spend"] >= min_spend]
    if interests:
        filtered = [c for c in filtered if any(i in c["interests"] for i in interests)]

    return filtered[:limit]


def query_customers(
    tier: Optional[str] = None,
    min_spend: Optional[int] = None,
    interests: Optional[List[str]] = None,
    limit: int = 50,
) -> List[Dict]:
    """Query customers from MongoDB, falling back to mock data."""
    client = _get_mongodb_client()

    if client is None:
        logger.info("Using mock customer data (MongoDB unavailable)")
        return _filter_mock_customers(tier, min_spend, interests, limit)

    try:
        db = client[settings.MONGODB_DATABASE]
        collection = db["customers"]

        query = {}
        if tier:
            query["tier"] = tier
        if min_spend:
            query["total_spend"] = {"$gte": min_spend}
        if interests:
            query["interests"] = {"$in": interests}

        customers = list(collection.find(query).limit(limit))

        for customer in customers:
            if "_id" in customer:
                customer["_id"] = str(customer["_id"])

        return customers

    except Exception as e:
        logger.error("MongoDB query error: %s", e)
        return _filter_mock_customers(tier, min_spend, interests, limit)
    finally:
        client.close()


def query_by_target_audience(target_audience: str) -> List[Dict]:
    """Query customers based on target audience description."""
    audience = target_audience.lower()

    if "new" in audience:
        return MOCK_PROSPECTS.copy()
    elif "platinum" in audience:
        return query_customers(tier="platinum")
    elif "diamond" in audience:
        return query_customers(tier="diamond")
    elif "gold" in audience:
        return query_customers(tier="gold")
    elif "high spend" in audience or "high-spend" in audience:
        return query_customers(min_spend=500000)
    else:
        return query_customers()
