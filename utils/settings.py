from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "settings.json"

DEFAULT_AUTOCHAT = "mention"
DEFAULT_LANGUAGE = "auto"
EARLY_TRIAL_LIMIT_DEFAULT = 15


class SettingsStore:
    def __init__(self, path: Path = SETTINGS_PATH) -> None:
        self.path = path
        self._lock = Lock()
        self._data: dict = {"channels": {}, "guilds": {}, "meta": {}}
        self._mtime: float | None = None
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._data = {"channels": {}, "guilds": {}, "meta": {}}
            self._mtime = None
            return
        try:
            mtime = self.path.stat().st_mtime
            if self._mtime is not None and mtime == self._mtime:
                return
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._data = raw
            self._data.setdefault("channels", {})
            self._data.setdefault("guilds", {})
            self._data.setdefault("meta", {})
            self._mtime = mtime
        except (json.JSONDecodeError, TypeError, OSError):
            self._data = {"channels": {}, "guilds": {}, "meta": {}}
            self._mtime = None

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        try:
            self._mtime = self.path.stat().st_mtime
        except OSError:
            self._mtime = None

    def get_autochat(self, channel_id: int) -> str:
        with self._lock:
            self._load()
            return self._data["channels"].get(str(channel_id), {}).get(
                "autochat",
                DEFAULT_AUTOCHAT,
            )

    def set_autochat(self, channel_id: int, mode: str) -> None:
        with self._lock:
            self._load()
            channel = self._data["channels"].setdefault(str(channel_id), {})
            channel["autochat"] = mode
            self._save()

    def get_language(self, guild_id: int | None) -> str:
        if guild_id is None:
            return DEFAULT_LANGUAGE
        with self._lock:
            self._load()
            return self._data["guilds"].get(str(guild_id), {}).get(
                "language",
                DEFAULT_LANGUAGE,
            )

    def set_language(self, guild_id: int, language: str) -> None:
        with self._lock:
            self._load()
            guild = self._data["guilds"].setdefault(str(guild_id), {})
            guild["language"] = language
            self._save()

    def get_watchlist(self, channel_id: int) -> bool:
        with self._lock:
            self._load()
            return bool(
                self._data["channels"].get(str(channel_id), {}).get("watchlist", False)
            )

    def set_watchlist(self, channel_id: int, enabled: bool) -> None:
        with self._lock:
            self._load()
            channel = self._data["channels"].setdefault(str(channel_id), {})
            channel["watchlist"] = enabled
            self._save()

    def get_premium(self, guild_id: int) -> bool:
        with self._lock:
            self._load()
            return bool(
                self._data["guilds"].get(str(guild_id), {}).get("premium", False)
            )

    def set_premium(
        self,
        guild_id: int,
        enabled: bool,
        *,
        ultra: bool = False,
        stripe_customer_id: str | None = None,
        stripe_subscription_id: str | None = None,
    ) -> None:
        with self._lock:
            self._load()
            guild = self._data["guilds"].setdefault(str(guild_id), {})
            guild["premium"] = enabled
            guild["ultra"] = bool(enabled and ultra)
            if enabled:
                guild["plan"] = "ultra" if ultra else "premium"
            else:
                guild["plan"] = "free"
                guild["ultra"] = False
            if stripe_customer_id is not None:
                guild["stripe_customer_id"] = stripe_customer_id
            if stripe_subscription_id is not None:
                guild["stripe_subscription_id"] = stripe_subscription_id
            if not enabled:
                guild.pop("stripe_subscription_id", None)
            self._save()

    def get_stripe_customer(self, guild_id: int) -> str | None:
        with self._lock:
            self._load()
            value = self._data["guilds"].get(str(guild_id), {}).get(
                "stripe_customer_id"
            )
            return str(value) if value else None

    def get_guild_plan(self, guild_id: int) -> dict:
        with self._lock:
            self._load()
            return dict(self._data["guilds"].get(str(guild_id), {}))

    def set_guild_trial(
        self,
        guild_id: int,
        *,
        started: str,
        ends: str,
        early_slot: bool,
    ) -> None:
        with self._lock:
            self._load()
            guild = self._data["guilds"].setdefault(str(guild_id), {})
            guild["trial_started"] = started
            guild["trial_ends"] = ends
            guild["early_slot"] = early_slot
            guild["premium"] = False
            self._save()

    def count_early_trials(self) -> int:
        with self._lock:
            self._load()
            return sum(
                1
                for guild in self._data["guilds"].values()
                if guild.get("early_slot")
            )

    def early_trial_limit(self) -> int:
        with self._lock:
            self._load()
            return int(
                self._data.get("meta", {}).get(
                    "early_trial_limit",
                    EARLY_TRIAL_LIMIT_DEFAULT,
                )
            )

    def guild_snapshot(self, guild_id: int) -> dict:
        with self._lock:
            self._load()
            guild = self._data["guilds"].get(str(guild_id), {})
            return {
                "language": guild.get("language", DEFAULT_LANGUAGE),
                "premium": bool(guild.get("premium", False)),
                "trial_ends": guild.get("trial_ends"),
                "early_slot": bool(guild.get("early_slot", False)),
                "channels": dict(self._data["channels"]),
            }


settings_store = SettingsStore()
