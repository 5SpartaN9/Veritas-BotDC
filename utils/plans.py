from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from utils.settings import settings_store

EARLY_TRIAL_LIMIT = 15   # fewer free demos = lower Gemini cost
EARLY_TRIAL_DAYS = 90

# Budget-friendly limits (Gemini costs money per request)
FREE_USER_RPM = 2          # per 10 minutes
PREMIUM_USER_RPM = 8
FREE_GUILD_DAILY = 15
PREMIUM_GUILD_DAILY = 80

PREMIUM_COMMANDS = {"debate", "multicheck", "watchcheck"}
PREMIUM_AUTOCHAT_MODES = {"questions", "all"}


@dataclass
class PlanInfo:
    plan: str  # free | trial | premium
    active: bool
    label: str
    trial_ends: str | None = None
    early_slot: bool = False
    slots_used: int = 0
    slots_limit: int = EARLY_TRIAL_LIMIT


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def get_plan_info(guild_id: int) -> PlanInfo:
    data = settings_store.get_guild_plan(guild_id)
    slots_used = settings_store.count_early_trials()
    if data.get("premium"):
        return PlanInfo(
            plan="premium",
            active=True,
            label="Premium",
            trial_ends=None,
            early_slot=bool(data.get("early_slot")),
            slots_used=slots_used,
        )

    ends = _parse_iso(data.get("trial_ends"))
    if ends and ends > _now():
        return PlanInfo(
            plan="trial",
            active=True,
            label="Demo / Trial",
            trial_ends=ends.date().isoformat(),
            early_slot=bool(data.get("early_slot")),
            slots_used=slots_used,
        )

    return PlanInfo(
        plan="free",
        active=False,
        label="Free",
        trial_ends=data.get("trial_ends"),
        early_slot=bool(data.get("early_slot")),
        slots_used=slots_used,
    )


def has_premium_features(guild_id: int | None) -> bool:
    if guild_id is None:
        return False
    return get_plan_info(guild_id).active


def ensure_early_trial(guild_id: int) -> PlanInfo:
    """Grant 3-month demo to first N servers that install the bot."""
    info = get_plan_info(guild_id)
    if info.plan in {"premium", "trial"} and info.active:
        return info

    data = settings_store.get_guild_plan(guild_id)
    # Already had a trial that expired — don't auto-renew
    if data.get("trial_ends") and not info.active and not data.get("premium"):
        return info

    if settings_store.count_early_trials() >= EARLY_TRIAL_LIMIT:
        return info

    started = _now()
    ends = started + timedelta(days=EARLY_TRIAL_DAYS)
    settings_store.set_guild_trial(
        guild_id,
        started=started.isoformat(),
        ends=ends.isoformat(),
        early_slot=True,
    )
    return get_plan_info(guild_id)


def user_rate_limit(guild_id: int | None) -> int:
    if guild_id is not None and has_premium_features(guild_id):
        return PREMIUM_USER_RPM
    return FREE_USER_RPM


def guild_daily_limit(guild_id: int | None) -> int:
    if guild_id is not None and has_premium_features(guild_id):
        return PREMIUM_GUILD_DAILY
    return FREE_GUILD_DAILY


def command_allowed(guild_id: int | None, command_name: str) -> bool:
    if command_name not in PREMIUM_COMMANDS:
        return True
    return has_premium_features(guild_id)


def autochat_mode_allowed(guild_id: int | None, mode: str) -> bool:
    if mode not in PREMIUM_AUTOCHAT_MODES:
        return True
    return has_premium_features(guild_id)


FREE_FEATURES = [
    "/ask, /check, /explain, /sources, /compare, /cite",
    "@Veritas mentions & reply fact-check",
    "Basic auto-chat (mentions)",
    f"{FREE_USER_RPM} AI requests / 10 min per user",
    f"{FREE_GUILD_DAILY} AI requests / day per server",
]

PREMIUM_FEATURES = [
    "Everything in Free",
    "/debate and /multicheck",
    "Watchlist (Check this? prompts)",
    "Auto-chat: questions / almost all",
    f"{PREMIUM_USER_RPM} AI requests / 10 min per user",
    f"{PREMIUM_GUILD_DAILY} AI requests / day per server",
    "Priority for heavier usage",
]
