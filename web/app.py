from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.plans import (
    FREE_FEATURES,
    PREMIUM_FEATURES,
    ULTRA_FEATURES,
    autochat_mode_allowed,
    ensure_early_trial,
    get_plan_info,
    has_premium_features,
)
from utils.settings import settings_store
from web.auth import current_session, current_user, router as auth_router
from web.config import (
    ADMINISTRATOR,
    DISCORD_CLIENT_SECRET,
    INVITE_URL,
    MANAGE_GUILD,
    PAYMENTS_ENABLED,
    PAYPAL_BUTTON_URL,
    PAYPAL_ME_URL,
    PREMIUM_PRICE_LABEL,
    SESSION_SECRET,
    ULTRA_LIFETIME_PRICE_LABEL,
    ULTRA_PRICE_LABEL,
    WEB_HOST,
    WEB_PORT,
)
from web.discord_api import fetch_bot_guild_ids, fetch_guild_channels
from web.payments import (
    activate_from_checkout_session,
    create_billing_portal,
    create_checkout_session,
    handle_webhook,
    stripe_ready,
)
from web.stripe_catalog import currency_options, label_for

WEB_DIR = Path(__file__).resolve().parent
SITE_DIR = ROOT / "website"

app = FastAPI(title="Veritas Dashboard")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False,
    max_age=60 * 60 * 24 * 7,
)
app.include_router(auth_router)

app.mount("/site", StaticFiles(directory=SITE_DIR), name="site")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))


def _can_manage(guild: dict) -> bool:
    try:
        perms = int(guild.get("permissions", 0))
    except (TypeError, ValueError):
        return False
    return bool(perms & ADMINISTRATOR or perms & MANAGE_GUILD)


def _require_user(request: Request) -> dict:
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _managed_guilds(session_data: dict, bot_guild_ids: set[str]) -> list[dict]:
    guilds = session_data.get("guilds") or []
    result = []
    for guild in guilds:
        gid = str(guild.get("id"))
        if not _can_manage(guild):
            continue
        item = dict(guild)
        item["bot_in_guild"] = gid in bot_guild_ids
        result.append(item)
    result.sort(key=lambda g: g.get("name", "").lower())
    return result


@app.get("/", response_class=HTMLResponse)
async def home_page(
    request: Request,
    code: str | None = None,
    state: str | None = None,
):
    if code and state:
        print("[auth] code arrived on /, forwarding to /auth/callback")
        return RedirectResponse(
            f"/auth/callback?code={code}&state={state}",
            status_code=303,
        )

    index = SITE_DIR / "index.html"
    html = index.read_text(encoding="utf-8")
    html = (
        html.replace('href="styles.css', 'href="/site/styles.css')
        .replace('src="script.js', 'src="/site/script.js')
        .replace('href="assets/', 'href="/site/assets/')
        .replace(
            '<a class="btn btn-small" href="#invite">Add to Discord</a>',
            '<a class="btn btn-small" href="/auth/login">Dashboard</a>',
        )
        .replace(
            '<nav class="nav-links">',
            '<nav class="nav-links"><a href="/auth/login">Dashboard</a>',
        )
    )
    return HTMLResponse(html)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    session_data = current_session(request)
    if not session_data or not session_data.get("user"):
        return RedirectResponse("/auth/login", status_code=303)

    user = session_data["user"]
    setup_needed = not bool(DISCORD_CLIENT_SECRET)
    bot_guild_ids: set[str] = set()
    error = None
    guilds: list[dict] = []
    if not setup_needed:
        try:
            bot_guild_ids = await fetch_bot_guild_ids()
            guilds = _managed_guilds(session_data, bot_guild_ids)
            for g in guilds:
                if g.get("bot_in_guild"):
                    ensure_early_trial(int(g["id"]))
                info = get_plan_info(int(g["id"]))
                g["plan"] = info.plan
                g["plan_label"] = info.label
                g["trial_ends"] = info.trial_ends
        except Exception as exc:
            error = str(exc)

    slots_used = settings_store.count_early_trials()
    ultra_slots_used = settings_store.count_early_ultra_trials()
    from utils.plans import EARLY_TRIAL_LIMIT, EARLY_ULTRA_TRIAL_LIMIT

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "guilds": guilds,
            "invite_url": INVITE_URL,
            "setup_needed": setup_needed,
            "error": error,
            "early_slots_used": slots_used,
            "early_slots_limit": EARLY_TRIAL_LIMIT,
            "ultra_slots_used": ultra_slots_used,
            "ultra_slots_limit": EARLY_ULTRA_TRIAL_LIMIT,
            "free_features": FREE_FEATURES,
            "premium_features": PREMIUM_FEATURES,
            "ultra_features": ULTRA_FEATURES,
            "premium_price": PREMIUM_PRICE_LABEL,
            "ultra_price": ULTRA_PRICE_LABEL,
            "lifetime_price": ULTRA_LIFETIME_PRICE_LABEL,
        },
    )


@app.get("/dashboard/{guild_id}", response_class=HTMLResponse)
async def guild_dashboard(request: Request, guild_id: str):
    session_data = current_session(request)
    if not session_data or not session_data.get("user"):
        return RedirectResponse("/auth/login", status_code=303)

    user = session_data["user"]
    guilds = session_data.get("guilds") or []
    guild = next((g for g in guilds if str(g.get("id")) == guild_id), None)
    if not guild or not _can_manage(guild):
        raise HTTPException(status_code=403, detail="No access to this server")

    bot_guild_ids: set[str] = set()
    bot_in = False
    channels = []
    try:
        bot_guild_ids = await fetch_bot_guild_ids()
        bot_in = guild_id in bot_guild_ids
    except Exception:
        bot_guild_ids = set()
        bot_in = False

    # Fallback unlock if Stripe webhooks failed but checkout succeeded
    if request.query_params.get("paid") == "1":
        session_id = request.query_params.get("session_id") or ""
        if session_id.startswith("cs_"):
            try:
                activate_from_checkout_session(session_id)
            except Exception:
                pass

    plan = get_plan_info(int(guild_id))
    if bot_in:
        try:
            plan = ensure_early_trial(int(guild_id))
        except Exception:
            plan = get_plan_info(int(guild_id))
        try:
            channels = await fetch_guild_channels(guild_id)
        except Exception:
            channels = []

    language = settings_store.get_language(int(guild_id))
    guild_plan_data = settings_store.get_guild_plan(int(guild_id))
    channel_settings = []
    for ch in channels:
        cid = int(ch["id"])
        channel_settings.append(
            {
                "id": ch["id"],
                "name": ch.get("name", "channel"),
                "autochat": settings_store.get_autochat(cid),
                "watchlist": settings_store.get_watchlist(cid),
            }
        )

    try:
        currencies = currency_options()
        price_map = {
            "premium": {c: label_for("premium", c) for c in ("USD", "EUR", "PLN", "RUB", "CNY")},
            "ultra": {c: label_for("ultra", c) for c in ("USD", "EUR", "PLN", "RUB", "CNY")},
            "lifetime": {
                c: label_for("ultra_lifetime", c) for c in ("USD", "EUR", "PLN", "RUB", "CNY")
            },
        }
    except Exception:
        currencies = [{"code": "USD", "name": "USD - US Dollar"}]
        price_map = {
            "premium": {"USD": PREMIUM_PRICE_LABEL},
            "ultra": {"USD": ULTRA_PRICE_LABEL},
            "lifetime": {"USD": ULTRA_LIFETIME_PRICE_LABEL},
        }

    return templates.TemplateResponse(
        request,
        "guild.html",
        {
            "user": user,
            "guild": guild,
            "bot_in": bot_in,
            "invite_url": INVITE_URL,
            "language": language,
            "plan": plan,
            "channels": channel_settings,
            "saved": request.query_params.get("saved") == "1",
            "paid": request.query_params.get("paid") == "1",
            "canceled": request.query_params.get("canceled") == "1",
            "free_features": FREE_FEATURES,
            "premium_features": PREMIUM_FEATURES,
            "ultra_features": ULTRA_FEATURES,
            "has_premium": plan.active,
            "payments_enabled": PAYMENTS_ENABLED,
            "price_label": PREMIUM_PRICE_LABEL,
            "ultra_price_label": ULTRA_PRICE_LABEL,
            "lifetime_price_label": ULTRA_LIFETIME_PRICE_LABEL,
            "paypal_url": PAYPAL_BUTTON_URL or PAYPAL_ME_URL,
            "is_paid_premium": plan.plan in {"premium", "ultra"},
            "is_ultra": plan.plan == "ultra",
            "is_lifetime": bool(guild_plan_data.get("lifetime")),
            "currency_options": currencies,
            "default_currency": "PLN",
            "price_by_currency": price_map,
        },
    )


@app.post("/dashboard/{guild_id}/checkout")
async def start_checkout(
    request: Request,
    guild_id: str,
    tier: str = Form("premium"),
    currency: str = Form("USD"),
):
    session_data = current_session(request)
    if not session_data or not session_data.get("user"):
        return RedirectResponse("/auth/login", status_code=303)

    guilds = session_data.get("guilds") or []
    guild = next((g for g in guilds if str(g.get("id")) == guild_id), None)
    if not guild or not _can_manage(guild):
        raise HTTPException(status_code=403, detail="No access")
    if tier not in {"premium", "ultra", "ultra_lifetime"}:
        tier = "premium"
    if not stripe_ready(tier, currency):
        raise HTTPException(
            status_code=503,
            detail="Payments are not configured yet. Add Stripe keys to .env",
        )

    user = session_data["user"]
    try:
        url = create_checkout_session(
            guild_id=guild_id,
            guild_name=str(guild.get("name") or "Server"),
            user_id=str(user.get("id")),
            user_email=user.get("email"),
            tier=tier,
            currency=currency,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}") from exc
    return RedirectResponse(url, status_code=303)


@app.post("/dashboard/{guild_id}/billing")
async def billing_portal(request: Request, guild_id: str):
    session_data = current_session(request)
    if not session_data or not session_data.get("user"):
        return RedirectResponse("/auth/login", status_code=303)

    guilds = session_data.get("guilds") or []
    guild = next((g for g in guilds if str(g.get("id")) == guild_id), None)
    if not guild or not _can_manage(guild):
        raise HTTPException(status_code=403, detail="No access")

    customer_id = settings_store.get_stripe_customer(int(guild_id))
    if not customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer for this server")
    try:
        url = create_billing_portal(customer_id=customer_id, guild_id=guild_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}") from exc
    return RedirectResponse(url, status_code=303)


@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        result = handle_webhook(payload, signature)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(result)


@app.post("/dashboard/{guild_id}/save")
async def save_guild_settings(
    request: Request,
    guild_id: str,
    language: str = Form("auto"),
):
    session_data = current_session(request)
    if not session_data or not session_data.get("user"):
        return RedirectResponse("/auth/login", status_code=303)

    guilds = session_data.get("guilds") or []
    guild = next((g for g in guilds if str(g.get("id")) == guild_id), None)
    if not guild or not _can_manage(guild):
        raise HTTPException(status_code=403, detail="No access")

    if language not in {"auto", "en", "pl", "ru", "zh"}:
        language = "auto"
    settings_store.set_language(int(guild_id), language)

    form = await request.form()
    bot_guild_ids = await fetch_bot_guild_ids()
    gid = int(guild_id)
    premium_ok = has_premium_features(gid)
    if guild_id in bot_guild_ids:
        channels = await fetch_guild_channels(guild_id)
        for ch in channels:
            cid = str(ch["id"])
            autochat = str(form.get(f"autochat_{cid}", "mention"))
            if autochat not in {"off", "mention", "questions", "all"}:
                autochat = "mention"
            if not autochat_mode_allowed(gid, autochat):
                autochat = "mention"
            settings_store.set_autochat(int(cid), autochat)
            watchlist = form.get(f"watchlist_{cid}") == "on"
            if watchlist and not premium_ok:
                watchlist = False
            settings_store.set_watchlist(int(cid), watchlist)

    return RedirectResponse(f"/dashboard/{guild_id}?saved=1", status_code=303)


def run() -> None:
    import uvicorn

    host = (WEB_HOST or "127.0.0.1").strip()
    # Guard against broken .env values like "127.0.0.1SOMETHING"
    if host not in {"127.0.0.1", "0.0.0.0", "localhost"} and not host.replace(".", "").isdigit():
        print(f"Invalid WEB_HOST={host!r}, falling back to 127.0.0.1")
        host = "127.0.0.1"

    uvicorn.run("web.app:app", host=host, port=WEB_PORT, reload=False)


if __name__ == "__main__":
    run()
