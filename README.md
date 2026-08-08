# Veritas BotDC

Discord bot with Google Gemini for fact-checking, Q&A, and music.

## Commands

| Command | Description |
|---------|-------------|
| `/check` | Fact-check a statement |
| `/ask` | Answer from scientific/official sources |
| `/sources` | Credible sources for a topic |
| `/explain` | Simple explanation + sources |
| `/compare` | Compare two claims |
| `/cite` | Extract quotes/data and verify |
| `/music` | Play YouTube/Spotify / search |
| `/skip` `/queue` `/pause` `/resume` `/nowplaying` `/stop` | Music controls |
| `/help` `/ping` `/history` `/panel` `/autochat` | Server utilities |
| Context menu **Verify claim** | Right-click a message to fact-check |
| `@Veritas` | Chat reply without slash commands |

AI replies in the **user's language**. UI/commands are in **English**.

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in keys. FFmpeg is required for music.

```bash
python bot.py
```

## Discord portal

Enable **Message Content Intent**. Invite with `bot` + `applications.commands`.

## Website, hosting & payments

See [DEPLOY.md](DEPLOY.md) for GitHub Pages (landing), Render (dashboard),
Stripe checkout, and PayPal.
