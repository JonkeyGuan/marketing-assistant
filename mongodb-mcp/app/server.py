import base64
import json
import logging
import os
import re
from typing import Any, List, Mapping, Optional

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from app.seed_data import CUSTOMERS as MOCK_CUSTOMERS, PROSPECTS as MOCK_PROSPECTS
from app.settings import settings

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


def decode_jwt_payload_unverified(token: str) -> dict[str, Any]:
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError("JWT must have three segments")
    payload_b64 = parts[1]
    pad = "=" * ((4 - len(payload_b64) % 4) % 4)
    raw = base64.urlsafe_b64decode(payload_b64 + pad)
    return json.loads(raw.decode("utf-8"))


def parse_authorization_bearer_jwt(headers: Mapping[str, Any]) -> dict[str, Any]:
    auth: Any = None
    for key in headers:
        if str(key).lower() == "authorization":
            auth = headers[key]
            break
    if auth is None:
        return {"preferred_username": None, "scope": None, "roles": [], "error": "missing_authorization"}
    if isinstance(auth, (list, tuple)):
        auth = auth[0] if auth else None
    if not auth or not isinstance(auth, str):
        return {"preferred_username": None, "scope": None, "roles": [], "error": "invalid_authorization_header"}
    m = re.match(r"^\s*Bearer\s+(\S+)\s*$", auth, re.IGNORECASE)
    if not m:
        return {"preferred_username": None, "scope": None, "roles": [], "error": "not_bearer_token"}
    try:
        claims = decode_jwt_payload_unverified(m.group(1))
    except Exception as e:
        logger.debug("JWT payload decode failed: %s", e)
        return {"preferred_username": None, "scope": None, "roles": [], "error": "jwt_decode_failed"}
    realm_access = claims.get("realm_access", {})
    roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
    return {
        "preferred_username": claims.get("preferred_username"),
        "scope": claims.get("scope"),
        "roles": roles,
    }


def _get_tier_config() -> tuple[str, str]:
    try:
        from app.vertical_config import _fetch_config
        cfg = _fetch_config()
        tiers = cfg.get("tiers", {})
        top = tiers.get("top", {})
        return top.get("role", "platinum-access"), top.get("id", "platinum")
    except Exception:
        return os.getenv("PLATINUM_ACCESS_ROLE", "platinum-access"), "platinum"


def filter_customers_by_user_perm(customers: list) -> list:
    headers = get_http_headers(include={"authorization"})
    auth_ctx = parse_authorization_bearer_jwt(headers)

    if not auth_ctx.get("preferred_username"):
        logger.info("No JWT token received — returning unfiltered data")
        return customers

    username = auth_ctx["preferred_username"]
    roles = auth_ctx.get("roles", [])
    platinum_role, platinum_tier = _get_tier_config()
    logger.info("JWT claims: preferred_username=%s roles=%s", username, roles)

    if platinum_role in roles:
        logger.info("%s has '%s' role — full access", username, platinum_role)
        return customers

    logger.info("%s lacks '%s' role — filtering out %s members", username, platinum_role, platinum_tier)
    return [c for c in customers if c.get("tier") != platinum_tier]


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
        return filter_customers_by_user_perm([c for c in MOCK_CUSTOMERS if c["tier"] == tier])[:limit]
    try:
        db = client[settings.MONGODB_DATABASE]
        customers = list(db.customers.find({"tier": tier}).limit(limit))
        for c in customers:
            if "_id" in c:
                c["_id"] = str(c["_id"])
        return filter_customers_by_user_perm(customers)
    except Exception as e:
        logger.error("Query error: %s", e)
        return filter_customers_by_user_perm([c for c in MOCK_CUSTOMERS if c["tier"] == tier])[:limit]
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
        return filter_customers_by_user_perm(filter_by_allowed_tiers(MOCK_CUSTOMERS, allowed_tiers))[:limit]
    try:
        db = client[settings.MONGODB_DATABASE]
        customers = list(db.customers.find().limit(limit))
        for c in customers:
            if "_id" in c:
                c["_id"] = str(c["_id"])
        return filter_customers_by_user_perm(filter_by_allowed_tiers(customers, allowed_tiers))
    except Exception as e:
        logger.error("Query error: %s", e)
        return filter_customers_by_user_perm(filter_by_allowed_tiers(MOCK_CUSTOMERS, allowed_tiers))[:limit]
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
        return filter_customers_by_user_perm([c for c in MOCK_CUSTOMERS if c.get("total_spend", 0) >= min_spend])[:limit]
    try:
        db = client[settings.MONGODB_DATABASE]
        customers = list(db.customers.find({"total_spend": {"$gte": min_spend}}).limit(limit))
        for c in customers:
            if "_id" in c:
                c["_id"] = str(c["_id"])
        return filter_customers_by_user_perm(customers)
    except Exception as e:
        logger.error("Query error: %s", e)
        return filter_customers_by_user_perm([c for c in MOCK_CUSTOMERS if c.get("total_spend", 0) >= min_spend])[:limit]
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
        return filter_customers_by_user_perm([
            c for c in MOCK_CUSTOMERS
            if query_lower in c.get("name", "").lower()
            or query_lower in c.get("name_en", "").lower()
            or query_lower in c.get("email", "").lower()
        ])[:limit]
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
        return filter_customers_by_user_perm(customers)
    except Exception as e:
        logger.error("Query error: %s", e)
        return filter_customers_by_user_perm([
            c for c in MOCK_CUSTOMERS
            if query_lower in c.get("name", "").lower()
            or query_lower in c.get("name_en", "").lower()
            or query_lower in c.get("email", "").lower()
        ])[:limit]
    finally:
        client.close()


@mcp.tool
def get_customer_count_by_tier() -> dict:
    """Get count of customers in each membership tier."""
    client = get_mongodb_client()
    if client is None:
        counts = {}
        for c in filter_customers_by_user_perm(list(MOCK_CUSTOMERS)):
            tier = c.get("tier", "unknown")
            counts[tier] = counts.get(tier, 0) + 1
        return counts
    try:
        db = client[settings.MONGODB_DATABASE]
        customers = list(db.customers.find())
        for c in customers:
            if "_id" in c:
                c["_id"] = str(c["_id"])
        filtered = filter_customers_by_user_perm(customers)
        counts = {}
        for c in filtered:
            tier = c.get("tier", "unknown")
            counts[tier] = counts.get(tier, 0) + 1
        return counts
    except Exception as e:
        logger.error("Query error: %s", e)
        counts = {}
        for c in filter_customers_by_user_perm(list(MOCK_CUSTOMERS)):
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
