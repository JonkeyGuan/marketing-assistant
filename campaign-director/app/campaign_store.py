import json
import logging
from datetime import datetime
from pathlib import Path

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
        self._disk_enabled = False
        self._storage_path: Path | None = None

    def init(self, storage_path: str):
        self._storage_path = Path(storage_path)
        try:
            self._storage_path.mkdir(parents=True, exist_ok=True)
            self._disk_enabled = True
            self._load_from_disk()
            logger.info("Campaign store: disk persistence enabled at %s, loaded %d campaigns",
                        self._storage_path, len(self._store))
        except OSError as e:
            logger.info("Campaign store: disk persistence disabled (%s), using memory-only", e)

    def _load_from_disk(self):
        from app.schemas import CampaignData
        for f in self._storage_path.glob("*.json"):
            try:
                obj = json.loads(f.read_text(encoding="utf-8"))
                campaign = CampaignData(**obj)
                self._store[campaign.id] = campaign
            except Exception as e:
                logger.warning("Failed to load campaign from %s: %s", f.name, e)

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
        if not self._disk_enabled or campaign_id not in self._store:
            return
        try:
            path = self._storage_path / f"{campaign_id}.json"
            path.write_text(self._serialize(self._store[campaign_id]), encoding="utf-8")
        except OSError as e:
            logger.warning("Failed to persist campaign %s: %s", campaign_id, e)

    def _remove_from_disk(self, campaign_id: str):
        if not self._disk_enabled:
            return
        try:
            path = self._storage_path / f"{campaign_id}.json"
            path.unlink(missing_ok=True)
        except OSError as e:
            logger.warning("Failed to remove campaign %s from disk: %s", campaign_id, e)

    def __setitem__(self, key, value):
        self._store[key] = value
        self.sync(key)

    def __getitem__(self, key):
        return self._store[key]

    def __contains__(self, key):
        return key in self._store

    def __delitem__(self, key):
        del self._store[key]
        self._remove_from_disk(key)

    def __len__(self):
        return len(self._store)

    def pop(self, key, *args):
        result = self._store.pop(key, *args)
        self._remove_from_disk(key)
        return result

    def get(self, key, default=None):
        return self._store.get(key, default)

    def values(self):
        return self._store.values()

    def keys(self):
        return self._store.keys()

    def items(self):
        return self._store.items()
