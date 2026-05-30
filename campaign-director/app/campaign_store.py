import json
import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


class CampaignStore:

    PERSIST_FIELDS = [
        "id", "campaign_name", "campaign_description", "hotel_name",
        "target_audience", "theme", "start_date", "end_date",
        "status", "created_at",
        "hero_image_url", "preview_url", "production_url",
        "email_subject_en", "email_body_en",
        "email_subject_zh", "email_body_zh",
        "customer_count",
        "customer_list",
    ]

    def __init__(self):
        self._store: dict = {}
        self._api_url: str = ""

    def init(self, api_url: str):
        self._api_url = api_url.rstrip("/")
        self._load_from_api()
        logger.info("Campaign store: using campaign-api at %s, loaded %d campaigns",
                     self._api_url, len(self._store))

    def _load_from_api(self):
        from app.schemas import CampaignData
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{self._api_url}/api/campaigns")
                if resp.status_code == 200:
                    for obj in resp.json():
                        try:
                            campaign = CampaignData(**obj)
                            self._store[campaign.id] = campaign
                        except Exception as e:
                            logger.warning("Failed to load campaign: %s", e)
        except Exception as e:
            logger.info("Campaign store: could not load from API (%s), starting empty", e)

    def _serialize(self, campaign) -> str:
        data = {}
        for field in self.PERSIST_FIELDS:
            val = getattr(campaign, field, None)
            if val is None:
                continue
            if isinstance(val, datetime):
                data[field] = val.isoformat()
            elif hasattr(val, "value"):
                data[field] = val.value
            elif isinstance(val, list):
                data[field] = [item.model_dump() if hasattr(item, "model_dump") else item for item in val]
            else:
                data[field] = val
        return json.dumps(data, ensure_ascii=False)

    def sync(self, campaign_id: str):
        if not self._api_url or campaign_id not in self._store:
            return
        import time
        for attempt in range(3):
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.put(
                        f"{self._api_url}/api/campaigns/{campaign_id}",
                        content=self._serialize(self._store[campaign_id]).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.status_code < 500:
                        return
                    logger.warning("Sync campaign %s: %s (attempt %d)", campaign_id, resp.status_code, attempt + 1)
            except Exception as e:
                logger.warning("Sync campaign %s failed (attempt %d): %s", campaign_id, attempt + 1, e)
            if attempt < 2:
                time.sleep(2)

    def __setitem__(self, key, value):
        self._store[key] = value
        self.sync(key)

    def __getitem__(self, key):
        return self._store[key]

    def __contains__(self, key):
        return key in self._store

    def __delitem__(self, key):
        del self._store[key]

    def __len__(self):
        return len(self._store)

    def pop(self, key, *args):
        return self._store.pop(key, *args)

    def get(self, key, default=None):
        return self._store.get(key, default)

    def values(self):
        return self._store.values()

    def keys(self):
        return self._store.keys()

    def items(self):
        return self._store.items()
