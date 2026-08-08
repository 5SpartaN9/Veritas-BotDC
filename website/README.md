# Veritas Web Panel

Landing page + Discord-login dashboard (ProBot-style configuration).

## 1. Discord Developer Portal

1. Open your app → **OAuth2**
2. Copy **Client Secret** into `.env` as `DISCORD_CLIENT_SECRET`
3. Add redirect URL:
   ```
   http://127.0.0.1:8000/auth/callback
   ```
4. Save changes

`.env` example:

```env
DISCORD_CLIENT_ID=1533047923829375056
DISCORD_CLIENT_SECRET=paste_secret_here
DISCORD_REDIRECT_URI=http://127.0.0.1:8000/auth/callback
SESSION_SECRET=any-long-random-string
DISCORD_TOKEN=your_bot_token
```

## 2. Install & run

```cmd
cd "C:\Users\joljo\OneDrive\Pulpit\Veritas BotDC"
venv\Scripts\activate
pip install -r requirements.txt
python -m web.app
```

Open:
- Landing: http://127.0.0.1:8000/
- Dashboard: http://127.0.0.1:8000/dashboard

## 3. What the dashboard can do

- Login with Discord
- List servers you can manage
- Set AI language (auto / EN / PL / RU / ZH)
- Per-channel auto-chat mode
- Per-channel watchlist

Settings are written to `data/settings.json` — the same file the bot reads.

## 4. Public hosting later

Deploy on a VPS with a domain, then set redirect to:

```text
https://your-domain.com/auth/callback
```

and update `DISCORD_REDIRECT_URI` + Portal redirects.
