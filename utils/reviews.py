from __future__ import annotations

import json
import re
import secrets
import time
from pathlib import Path
from threading import Lock
from typing import Any

from utils.paths import DATA_DIR

REVIEWS_PATH = DATA_DIR / "reviews.json"
MAX_NAME = 40
MAX_TEXT = 500
MAX_REVIEWS_RETURN = 40
RATE_LIMIT_SECONDS = 90

_NAME_OK = re.compile(r"^[\w\s.\-']+$", re.UNICODE)


class ReviewStore:
    def __init__(self, path: Path = REVIEWS_PATH) -> None:
        self.path = path
        self._lock = Lock()
        self._rate: dict[str, float] = {}

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                return [r for r in raw if isinstance(r, dict)]
        except (json.JSONDecodeError, OSError, TypeError):
            pass
        return []

    def _save(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_public(self, limit: int = MAX_REVIEWS_RETURN) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._load()
        visible = [r for r in rows if r.get("published", True)]
        visible.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
        out = []
        for r in visible[:limit]:
            out.append(
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "stars": int(r.get("stars", 0)),
                    "text": r.get("text"),
                    "created_at": r.get("created_at"),
                }
            )
        return out

    def average_stars(self) -> float | None:
        rows = self.list_public(limit=500)
        if not rows:
            return None
        total = sum(int(r["stars"]) for r in rows)
        return round(total / len(rows), 1)

    def add(
        self,
        *,
        name: str,
        stars: int,
        text: str,
        client_key: str,
    ) -> dict[str, Any]:
        clean_name = " ".join((name or "").strip().split())[:MAX_NAME]
        clean_text = " ".join((text or "").strip().split())[:MAX_TEXT]
        if len(clean_name) < 2:
            raise ValueError("Name is too short")
        if not _NAME_OK.match(clean_name):
            raise ValueError("Name has invalid characters")
        if stars < 1 or stars > 5:
            raise ValueError("Stars must be 1–5")
        if len(clean_text) < 12:
            raise ValueError("Review is too short")

        now = time.time()
        with self._lock:
            last = self._rate.get(client_key, 0.0)
            if now - last < RATE_LIMIT_SECONDS:
                raise ValueError("Please wait a minute before posting again")
            self._rate[client_key] = now

            # prune old rate keys
            if len(self._rate) > 500:
                cutoff = now - RATE_LIMIT_SECONDS * 2
                self._rate = {k: v for k, v in self._rate.items() if v >= cutoff}

            row = {
                "id": secrets.token_urlsafe(8),
                "name": clean_name,
                "stars": int(stars),
                "text": clean_text,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "published": True,
            }
            rows = self._load()
            rows.append(row)
            self._save(rows)
            return {
                "id": row["id"],
                "name": row["name"],
                "stars": row["stars"],
                "text": row["text"],
                "created_at": row["created_at"],
            }

    def delete(self, review_id: str) -> bool:
        rid = (review_id or "").strip()
        if not rid:
            return False
        with self._lock:
            rows = self._load()
            keep = [r for r in rows if str(r.get("id")) != rid]
            if len(keep) == len(rows):
                return False
            self._save(keep)
            return True


review_store = ReviewStore()
