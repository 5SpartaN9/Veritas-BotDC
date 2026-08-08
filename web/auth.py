from __future__ import annotations

import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from web.config import (
    DISCORD_CLIENT_ID,
    DISCORD_CLIENT_SECRET,
    DISCORD_REDIRECT_URI,
    OAUTH_AUTHORIZE,
    OAUTH_TOKEN,
    SESSION_SECRET,
)
from web.discord_api import discord_api

router = APIRouter(prefix="/auth")
_state_s = URLSafeTimedSerializer(SESSION_SECRET, salt="veritas-oauth-state")
_session_s = URLSafeTimedSerializer(SESSION_SECRET, salt="veritas-user-session")

COOKIE_NAME = "veritas_session"


def _make_state() -> str:
    return _state_s.dumps({"nonce": secrets.token_urlsafe(12)})


def _check_state(state: str) -> bool:
    try:
        _state_s.loads(state, max_age=900)
        return True
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return False


def dump_user_session(payload: dict[str, Any]) -> str:
    return _session_s.dumps(payload)


def load_user_session(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        data = _session_s.loads(token, max_age=60 * 60 * 24 * 14)
        if isinstance(data, dict) and data.get("user"):
            return data
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None
    return None


def login_url(state: str) -> str:
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": DISCORD_REDIRECT_URI,
        "scope": "identify guilds",
        "state": state,
    }
    return f"{OAUTH_AUTHORIZE}?{urlencode(params)}"


def _set_session_cookie(response: RedirectResponse, payload: dict[str, Any]) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=dump_user_session(payload),
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 24 * 14,
        path="/",
    )


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    if not DISCORD_CLIENT_SECRET:
        return HTMLResponse(
            "<h1>Missing DISCORD_CLIENT_SECRET</h1>"
            "<p>Add it to .env and restart the panel.</p>",
            status_code=500,
        )
    # Already logged in?
    existing = load_user_session(request.cookies.get(COOKIE_NAME))
    if existing:
        return RedirectResponse("/dashboard", status_code=303)

    state = _make_state()
    print(f"[auth] login start → redirect Discord (state ok)")
    return RedirectResponse(login_url(state), status_code=303)


@router.get("/callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    print(f"[auth] callback hit code={bool(code)} state={bool(state)} error={error}")

    if error:
        return HTMLResponse(
            f"<h1>Discord OAuth error</h1><p>{error}: {error_description}</p>"
            "<p><a href='/auth/login'>Try again</a></p>",
            status_code=400,
        )
    if not code or not state:
        return HTMLResponse(
            "<h1>Missing OAuth code</h1>"
            "<p>Redirect URL in Discord must be exactly:</p>"
            f"<pre>{DISCORD_REDIRECT_URI}</pre>"
            "<p><a href='/auth/login'>Try again</a></p>",
            status_code=400,
        )
    if not _check_state(state):
        return HTMLResponse(
            "<h1>Invalid/expired login state</h1>"
            "<p><a href='/auth/login'>Start login again</a></p>",
            status_code=400,
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        token_res = await client.post(
            OAUTH_TOKEN,
            data={
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": DISCORD_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        print(f"[auth] token status={token_res.status_code}")
        if token_res.status_code >= 400:
            return HTMLResponse(
                "<h1>Token exchange failed</h1>"
                f"<pre>{token_res.text[:800]}</pre>"
                "<p>Check Client Secret + Redirect URL.</p>"
                "<p><a href='/auth/login'>Try again</a></p>",
                status_code=400,
            )
        token_data = token_res.json()

    access_token = token_data["access_token"]
    try:
        user = await discord_api("GET", "/users/@me", token=access_token)
        guilds = await discord_api("GET", "/users/@me/guilds", token=access_token)
    except Exception as exc:
        return HTMLResponse(
            f"<h1>Could not fetch Discord profile</h1><pre>{exc}</pre>"
            "<p><a href='/auth/login'>Try again</a></p>",
            status_code=400,
        )

    payload = {
        "user": {
            "id": str(user["id"]),
            "username": user.get("global_name") or user.get("username"),
            "avatar": user.get("avatar"),
        },
        "guilds": guilds,
        "access_token": access_token,
    }
    print(f"[auth] login ok user={payload['user']['username']} guilds={len(guilds)}")

    response = RedirectResponse("/dashboard", status_code=303)
    _set_session_cookie(response, payload)
    # Also mirror into Starlette session for compatibility
    request.session["user"] = payload["user"]
    request.session["guilds"] = guilds
    request.session["access_token"] = access_token
    return response


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(COOKIE_NAME, path="/")
    request.session.clear()
    return response


def current_user(request: Request) -> dict[str, Any] | None:
    data = load_user_session(request.cookies.get(COOKIE_NAME))
    if data:
        return data.get("user")
    return request.session.get("user")


def current_session(request: Request) -> dict[str, Any] | None:
    data = load_user_session(request.cookies.get(COOKIE_NAME))
    if data:
        return data
    user = request.session.get("user")
    if not user:
        return None
    return {
        "user": user,
        "guilds": request.session.get("guilds") or [],
        "access_token": request.session.get("access_token"),
    }
