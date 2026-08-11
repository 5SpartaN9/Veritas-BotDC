from __future__ import annotations

import json
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from utils.paths import DATA_DIR

HISTORY_PATH = DATA_DIR / "history.json"
MAX_ENTRIES = 200


@dataclass
class HistoryEntry:
    timestamp: str
    guild_id: int
    channel_id: int
    user_id: int
    command: str
    preview: str
    summary: str


class HistoryStore:
    def __init__(self, path: Path = HISTORY_PATH, maxlen: int = MAX_ENTRIES) -> None:
        self.path = path
        self.maxlen = maxlen
        self._lock = Lock()
        self._entries: deque[HistoryEntry] = deque(maxlen=maxlen)
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for item in raw[-self.maxlen :]:
                self._entries.append(HistoryEntry(**item))
        except (json.JSONDecodeError, TypeError, KeyError):
            self._entries.clear()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(entry) for entry in self._entries]
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(
        self,
        *,
        guild_id: int,
        channel_id: int,
        user_id: int,
        command: str,
        preview: str,
        summary: str,
    ) -> None:
        entry = HistoryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            guild_id=guild_id,
            channel_id=channel_id,
            user_id=user_id,
            command=command,
            preview=preview[:180],
            summary=summary[:220],
        )
        with self._lock:
            self._entries.append(entry)
            self._save()

    def for_channel(self, channel_id: int, limit: int = 10) -> list[HistoryEntry]:
        with self._lock:
            items = [e for e in self._entries if e.channel_id == channel_id]
        return list(reversed(items[-limit:]))


history_store = HistoryStore()
