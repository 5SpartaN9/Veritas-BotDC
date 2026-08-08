from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from threading import Lock

CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "cache.json"
DEFAULT_TTL = 60 * 60 * 24  # 24h
MAX_ENTRIES = 500


class ResponseCache:
    def __init__(self, path: Path = CACHE_PATH, ttl: int = DEFAULT_TTL) -> None:
        self.path = path
        self.ttl = ttl
        self._lock = Lock()
        self._data: dict[str, dict] = {}
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

    @staticmethod
    def make_key(command: str, text: str, language: str) -> str:
        normalized = " ".join(text.lower().split())
        raw = f"{command}|{language}|{normalized}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> str | None:
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            if time.time() - item.get("ts", 0) > self.ttl:
                self._data.pop(key, None)
                self._save()
                return None
            return item.get("text")

    def set(self, key: str, text: str) -> None:
        with self._lock:
            self._data[key] = {"ts": time.time(), "text": text}
            if len(self._data) > MAX_ENTRIES:
                oldest = sorted(self._data.items(), key=lambda x: x[1].get("ts", 0))
                for k, _ in oldest[: len(self._data) - MAX_ENTRIES]:
                    self._data.pop(k, None)
            self._save()


response_cache = ResponseCache()
