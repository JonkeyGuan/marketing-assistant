import logging
from typing import List, Optional

from fastmcp import FastMCP
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
from starlette.requests import Request

from app.settings import settings
from app.seed_data import CUSTOMERS as MOCK_CUSTOMERS, PROSPECTS as MOCK_PROSPECTS

logger = logging.getLogger("mongodb_mcp")

TIER_SCOPES = {
    "tier-admin": ["diamond", "platinum", "gold"],
    "tier-diamond": ["diamond", "platinum", "gold"],
    "tier-platinum": ["platinum", "gold"],
    "tier-gold": ["gold"],
}


def filter_by_allowed_tiers(customers: list, allowed_tiers: str = "") -> list:
    if not allowed_tiers:
        return customers
    tiers = TIER_SCOPES.get(allowed_tiers, allowed_tiers.split(","))
    return [c for c in customers if c.get("tier", "") in tiers]


mcp = FastMCP("Customer Database MCP")


def get_mongodb_client() -> Optional[MongoClient]:
    try:
        client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)
        client.server_info()
        return client
    except ConnectionFailure as e:
        logger.warning("MongoDB connection failed: %s", e)
        return None


@mcp.tool
def get_customers_by_tier(tier: str, limit: int = 50) -> List[dict]:
    """Retrieve VIP customers by membership tier.

    Args:
        tier: Membership tier (platinum, gold, diamond)
        limit: Maximum number of customers to return
    """
    client = get_mongodb_client()
    if client is None:
        return [c for c in MOCK_CUSTOMERS if c["tier"] == tier][:limit]
    try:
        db = client[settings.MONGODB_DATABASE]
        customers = list(db.customers.find({"tier": tier}).limit(limit))
        for c in customers:
            if "_id" in c:
                c["_id"] = str(c["_id"])
        return customers
    except Exception as e:
        logger.error("Query error: %s", e)
        return [c for c in MOCK_CUSTOMERS if c["tier"] == tier][:limit]
    finally:
        client.close()


@mcp.tool
def get_prospects(limit: int = 50) -> List[dict]:
    """Retrieve prospect list for new member campaigns.

    Args:
        limit: Maximum number of prospects to return
    """
    client = get_mongodb_client()
    if client is None:
        return MOCK_PROSPECTS[:limit]
    try:
        db = client[settings.MONGODB_DATABASE]
        prospects = list(db.prospects.find().limit(limit))
        for p in prospects:
            if "_id" in p:
                p["_id"] = str(p["_id"])
        return prospects
    except Exception as e:
        logger.error("Query error: %s", e)
        return MOCK_PROSPECTS[:limit]
    finally:
        client.close()


@mcp.tool
def get_all_vip_customers(limit: int = 100, allowed_tiers: str = "") -> List[dict]:
    """Retrieve all VIP customers regardless of tier.

    Args:
        limit: Maximum number of customers to return
        allowed_tiers: Optional role-based filter (e.g., 'tier-admin', 'tier-gold')
    """
    client = get_mongodb_client()
    if client is None:
        return filter_by_allowed_tiers(MOCK_CUSTOMERS, allowed_tiers)[:limit]
    try:
        db = client[settings.MONGODB_DATABASE]
        customers = list(db.customers.find().limit(limit))
        for c in customers:
            if "_id" in c:
                c["_id"] = str(c["_id"])
        return filter_by_allowed_tiers(customers, allowed_tiers)
    except Exception as e:
        logger.error("Query error: %s", e)
        return filter_by_allowed_tiers(MOCK_CUSTOMERS, allowed_tiers)[:limit]
    finally:
        client.close()


@mcp.tool
def get_high_spend_customers(min_spend: int = 500000, limit: int = 50) -> List[dict]:
    """Retrieve customers with total spend above threshold.

    Args:
        min_spend: Minimum total spend amount
        limit: Maximum number of customers to return
    """
    client = get_mongodb_client()
    if client is None:
        return [c for c in MOCK_CUSTOMERS if c.get("total_spend", 0) >= min_spend][:limit]
    try:
        db = client[settings.MONGODB_DATABASE]
        customers = list(db.customers.find({"total_spend": {"$gte": min_spend}}).limit(limit))
        for c in customers:
            if "_id" in c:
                c["_id"] = str(c["_id"])
        return customers
    except Exception as e:
        logger.error("Query error: %s", e)
        return [c for c in MOCK_CUSTOMERS if c.get("total_spend", 0) >= min_spend][:limit]
    finally:
        client.close()


@mcp.tool
def search_customers(query: str, limit: int = 20) -> List[dict]:
    """Search customers by name or email.

    Args:
        query: Search string to match against name or email
        limit: Maximum number of customers to return
    """
    client = get_mongodb_client()
    query_lower = query.lower()
    if client is None:
        return [
            c for c in MOCK_CUSTOMERS
            if query_lower in c.get("name", "").lower()
            or query_lower in c.get("name_en", "").lower()
            or query_lower in c.get("email", "").lower()
        ][:limit]
    try:
        db = client[settings.MONGODB_DATABASE]
        customers = list(db.customers.find({
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"name_en": {"$regex": query, "$options": "i"}},
                {"email": {"$regex": query, "$options": "i"}}
            ]
        }).limit(limit))
        for c in customers:
            if "_id" in c:
                c["_id"] = str(c["_id"])
        return customers
    except Exception as e:
        logger.error("Query error: %s", e)
        return [
            c for c in MOCK_CUSTOMERS
            if query_lower in c.get("name", "").lower()
            or query_lower in c.get("name_en", "").lower()
            or query_lower in c.get("email", "").lower()
        ][:limit]
    finally:
        client.close()


@mcp.tool
def get_customer_count_by_tier() -> dict:
    """Get count of customers in each membership tier."""
    client = get_mongodb_client()
    if client is None:
        counts = {}
        for c in MOCK_CUSTOMERS:
            tier = c.get("tier", "unknown")
            counts[tier] = counts.get(tier, 0) + 1
        return counts
    try:
        db = client[settings.MONGODB_DATABASE]
        pipeline = [{"$group": {"_id": "$tier", "count": {"$sum": 1}}}]
        result = list(db.customers.aggregate(pipeline))
        return {r["_id"]: r["count"] for r in result}
    except Exception as e:
        logger.error("Query error: %s", e)
        counts = {}
        for c in MOCK_CUSTOMERS:
            tier = c.get("tier", "unknown")
            counts[tier] = counts.get(tier, 0) + 1
        return counts
    finally:
        client.close()


async def health(request: Request):
    return JSONResponse({"status": "healthy", "service": "MongoDB MCP"})


mcp_app = mcp.http_app(path="/mcp")

app = Starlette(
    routes=[
        Route("/healthz", health, methods=["GET"]),
        Route("/readyz", health, methods=["GET"]),
        Mount("/", app=mcp_app),
    ],
    lifespan=mcp_app.lifespan,
)
