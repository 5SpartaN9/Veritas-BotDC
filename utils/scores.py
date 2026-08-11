from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from utils.paths import DATA_DIR

SCORES_PATH = DATA_DIR / "scores.json"


class ScoreStore:
    def __init__(self, path: Path = SCORES_PATH) -> None:
        self.path = path
        self._lock = Lock()
        self._data: dict[str, dict[str, int]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._data = raw
        except (json.JSONDecodeError, TypeError):
            self._data = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def record(self, user_id: int, verdict: str) -> None:
        key = str(user_id)
        upper = verdict.upper()
        bucket = "other"
        if "PARTLY" in upper:
            bucket = "partly"
        elif "UNVERIFIED" in upper or "INSUFFICIENT" in upper or "NO DATA" in upper:
            bucket = "unverified"
        elif "FALSE" in upper or "NOT CONFIRMED" in upper or "NOT_CONFIRMED" in upper:
            bucket = "false"
        elif upper.strip().startswith("TRUE") or upper.strip() == "CONFIRMED" or " CONFIRMED" in f" {upper}":
            if "NOT" not in upper:
                bucket = "true"

        with self._lock:
            entry = self._data.setdefault(
                key,
                {"true": 0, "false": 0, "partly": 0, "unverified": 0, "other": 0, "total": 0},
            )
            entry[bucket] = entry.get(bucket, 0) + 1
            entry["total"] = entry.get("total", 0) + 1
            self._save()

    def get(self, user_id: int) -> dict[str, int]:
        with self._lock:
            entry = self._data.get(str(user_id))
            if not entry:
                return {"true": 0, "false": 0, "partly": 0, "unverified": 0, "other": 0, "total": 0}
            return dict(entry)


score_store = ScoreStore()
