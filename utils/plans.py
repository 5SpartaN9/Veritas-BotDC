from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from utils.settings import settings_store

EARLY_TRIAL_LIMIT = 15  # Premium demo slots
EARLY_ULTRA_TRIAL_LIMIT = 10  # Ultra demo slots (separate)
EARLY_TRIAL_DAYS = 90

# Limits sized so paid plans stay modestly profitable at max use
# (~4.5 gr / AI ask). Caps are the product, not “infinite AI”.
FREE_USER_RPM = 2  # per 10 minutes
PREMIUM_USER_RPM = 5
ULTRA_USER_RPM = 10

FREE_GUILD_DAILY = 10
PREMIUM_GUILD_DAILY = 12
ULTRA_GUILD_DAILY = 35  # busy servers, still safe vs Gemini cost

PREMIUM_COMMANDS = {"debate", "multicheck", "watchcheck"}
PREMIUM_AUTOCHAT_MODES = {"questions", "all"}


@dataclass
class PlanInfo:
    plan: str  # free | trial | premium | ultra
    active: bool
    label: str
    trial_ends: str | None = None
    early_slot: bool = False
    early_ultra_slot: bool = False
    slots_used: int = 0
    slots_limit: int = EARLY_TRIAL_LIMIT
    ultra_slots_used: int = 0
    ultra_slots_limit: int = EARLY_ULTRA_TRIAL_LIMIT
    is_trial: bool = False


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


def _slot_counts() -> tuple[int, int]:
    return (
        settings_store.count_early_trials(),
        settings_store.count_early_ultra_trials(),
    )


def get_plan_info(guild_id: int) -> PlanInfo:
    data = settings_store.get_guild_plan(guild_id)
    slots_used, ultra_slots_used = _slot_counts()
    early_slot = bool(data.get("early_slot"))
    early_ultra_slot = bool(data.get("early_ultra_slot"))
    ends = _parse_iso(data.get("trial_ends"))
    trial_active = bool(ends and ends > _now())

    base = dict(
        early_slot=early_slot,
        early_ultra_slot=early_ultra_slot,
        slots_used=slots_used,
        slots_limit=EARLY_TRIAL_LIMIT,
        ultra_slots_used=ultra_slots_used,
        ultra_slots_limit=EARLY_ULTRA_TRIAL_LIMIT,
    )

    paid_ultra = bool(data.get("lifetime")) or (
        bool(data.get("premium"))
        and (bool(data.get("ultra")) or data.get("plan") == "ultra")
    )
    # Paid Ultra / Lifetime always win over a leftover ultra_trial flag.
    if paid_ultra:
        label = "Ultra Lifetime" if data.get("lifetime") else "Ultra Premium"
        return PlanInfo(
            plan="ultra",
            active=True,
            label=label,
            trial_ends=None,
            is_trial=False,
            **base,
        )

    # Active Ultra early demo (full Ultra limits)
    if data.get("ultra_trial") and trial_active:
        return PlanInfo(
            plan="ultra",
            active=True,
            label="Ultra Demo",
            trial_ends=ends.date().isoformat() if ends else None,
            is_trial=True,
            **base,
        )

    if data.get("premium") or data.get("plan") == "premium":
        return PlanInfo(
            plan="premium",
            active=True,
            label="Premium",
            trial_ends=None,
            is_trial=False,
            **base,
        )

    # Active Premium early demo
    if trial_active and not data.get("ultra_trial"):
        return PlanInfo(
            plan="trial",
            active=True,
            label="Premium Demo",
            trial_ends=ends.date().isoformat() if ends else None,
            is_trial=True,
            **base,
        )

    return PlanInfo(
        plan="free",
        active=False,
        label="Free",
        trial_ends=data.get("trial_ends"),
        is_trial=False,
        **base,
    )


def has_premium_features(guild_id: int | None) -> bool:
    """Premium, Ultra, or active demo trial."""
    if guild_id is None:
        return False
    return get_plan_info(guild_id).active


def has_ultra_features(guild_id: int | None) -> bool:
    if guild_id is None:
        return False
    return get_plan_info(guild_id).plan == "ultra"


def ensure_early_trial(guild_id: int) -> PlanInfo:
    """Grant early demos: first 10 servers → Ultra 90d; next Premium slots → Premium 90d."""
    info = get_plan_info(guild_id)
    if info.plan in {"premium", "ultra"} and info.active and not info.is_trial:
        return info
    if info.active and info.is_trial:
        return info

    data = settings_store.get_guild_plan(guild_id)
    # Never overwrite a paid / Stripe-backed plan with a demo slot.
    if (
        data.get("premium")
        or data.get("lifetime")
        or data.get("stripe_subscription_id")
        or data.get("stripe_customer_id")
    ):
        return info

    # Already used a trial that expired — don't auto-renew
    if data.get("trial_ends") and not info.active:
        return info

    started = _now()
    ends = started + timedelta(days=EARLY_TRIAL_DAYS)

    ultra_used = settings_store.count_early_ultra_trials()
    if ultra_used < EARLY_ULTRA_TRIAL_LIMIT:
        settings_store.set_guild_trial(
            guild_id,
            started=started.isoformat(),
            ends=ends.isoformat(),
            early_slot=True,
            ultra=True,
        )
        return get_plan_info(guild_id)

    premium_used = settings_store.count_early_trials()
    if premium_used < EARLY_TRIAL_LIMIT:
        settings_store.set_guild_trial(
            guild_id,
            started=started.isoformat(),
            ends=ends.isoformat(),
            early_slot=True,
            ultra=False,
        )
        return get_plan_info(guild_id)

    return info


def user_rate_limit(guild_id: int | None) -> int:
    if guild_id is None:
        return FREE_USER_RPM
    info = get_plan_info(guild_id)
    if info.plan == "ultra":
        return ULTRA_USER_RPM
    if info.active:
        return PREMIUM_USER_RPM
    return FREE_USER_RPM


def guild_daily_limit(guild_id: int | None) -> int:
    if guild_id is None:
        return FREE_GUILD_DAILY
    info = get_plan_info(guild_id)
    if info.plan == "ultra":
        return ULTRA_GUILD_DAILY
    if info.active:
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
]

ULTRA_FEATURES = [
    "Everything in Premium",
    "Higher limits for busy / large communities",
    f"{ULTRA_USER_RPM} AI requests / 10 min per user",
    f"{ULTRA_GUILD_DAILY} AI requests / day per server",
    f"First {EARLY_ULTRA_TRIAL_LIMIT} servers: 3 months Ultra free",
    "Optional Ultra Lifetime — pay once, keep forever",
]
