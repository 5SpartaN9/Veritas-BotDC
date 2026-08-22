from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Lock

from utils.plans import FREE_GUILD_DAILY, guild_daily_limit, user_rate_limit

WINDOW_SECONDS = 10 * 60


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[int, deque[float]] = defaultdict(deque)
        self._guild_day: dict[str, dict[str, int]] = {}
        self._lock = Lock()

    def peek_user(self, user_id: int, guild_id: int | None) -> tuple[int, int, int]:
        """Return (used, limit, seconds_until_slot) without consuming a request."""
        limit = user_rate_limit(guild_id)
        now = time.monotonic()
        with self._lock:
            q = self._hits[user_id]
            while q and now - q[0] > WINDOW_SECONDS:
                q.popleft()
            used = len(q)
            if used >= limit and q:
                retry = int(WINDOW_SECONDS - (now - q[0])) + 1
                return used, limit, max(retry, 1)
            return used, limit, 0

    def peek_guild_daily(self, guild_id: int | None) -> tuple[int, int]:
        """Return (used, limit) for today's server quota without consuming."""
        if guild_id is None:
            return 0, FREE_GUILD_DAILY
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = str(guild_id)
        limit = guild_daily_limit(guild_id)
        with self._lock:
            entry = self._guild_day.get(key)
            if not entry or entry.get("day") != day:
                return 0, limit
            return int(entry.get("count", 0)), limit

    def check_user(self, user_id: int, guild_id: int | None) -> tuple[bool, int]:
        limit = user_rate_limit(guild_id)
        now = time.monotonic()
        with self._lock:
            q = self._hits[user_id]
            while q and now - q[0] > WINDOW_SECONDS:
                q.popleft()
            if len(q) >= limit:
                retry = int(WINDOW_SECONDS - (now - q[0])) + 1
                return False, max(retry, 1)
            q.append(now)
            return True, 0

    def check_guild_daily(self, guild_id: int | None) -> tuple[bool, int]:
        if guild_id is None:
            return True, FREE_GUILD_DAILY
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = str(guild_id)
        limit = guild_daily_limit(guild_id)
        with self._lock:
            entry = self._guild_day.setdefault(key, {"day": day, "count": 0})
            if entry["day"] != day:
                entry["day"] = day
                entry["count"] = 0
            if entry["count"] >= limit:
                return False, 0
            entry["count"] += 1
            return True, limit - entry["count"]

    # Backwards-compatible helper
    def check(self, user_id: int, guild_id: int | None = None) -> tuple[bool, int]:
        ok, retry = self.check_user(user_id, guild_id)
        if not ok:
            return False, retry
        ok_g, _ = self.check_guild_daily(guild_id)
        if not ok_g:
            return False, 86400
        return True, 0


rate_limiter = RateLimiter()
