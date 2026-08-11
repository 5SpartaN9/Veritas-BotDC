# Hosting Veritas 24/7 (prosto)

Żeby bot działał nawet gdy wyłączysz komputer, wrzucamy go na internet
(Render.com). To jak wynajem małego komputera w chmurze.

## Co dostaniesz
- Bot Discord online non-stop
- Panel www (logowanie Discord + ustawienia)

## Koszt (orientacyjnie)
Render **Starter** ≈ kilka–kilkanaście USD / miesiąc za 2 usługi
(bot + panel). Darmowy plan **nie nadaje się** — bot by zasypiał.

---

## Krok 1 — Konto Render
1. Wejdź na https://render.com
2. Zarejestruj się przez **GitHub** (konto `5SpartaN9`)
3. Zatwierdź dostęp do repozytorium **Veritas-BotDC**

## Krok 2 — Wdróż projekt
1. W Render: **New** → **Blueprint**
2. Wybierz repo **Veritas-BotDC**
3. Render przeczyta plik `render.yaml` i zaproponuje usługę **veritas**
   (bot Discord + panel www w jednym miejscu)
4. Kliknij **Apply**

## Krok 3 — Wpisz tajne dane (Environment)
W usłudze **veritas** → **Environment** uzupełnij z Twojego `.env`:

- `DISCORD_TOKEN`
- `DISCORD_CLIENT_ID`
- `DISCORD_CLIENT_SECRET`
- `GOOGLE_API_KEY`

Ustaw też:

- `PUBLIC_BASE_URL` = `https://veritas-xxxx.onrender.com`  
  (dokładny adres zobaczysz w Render po starcie)
- `DISCORD_REDIRECT_URI` = `https://TEN-SAM-ADRES/auth/callback`

`GEMINI_MODEL` możesz zostawić: `gemini-flash-latest`

Stripe (płatności) możesz dodać później.

## Krok 4 — Discord Developer Portal
1. Wejdź w swoją aplikację Discord → **OAuth2** → Redirects
2. Dodaj: `https://TWOJ-PANEL.onrender.com/auth/callback`
3. Zapisz

## Krok 5 — Sprawdź
1. W Render status usług = **Live**
2. Wejdź na adres panelu
3. Na Discordzie bot powinien być **online** (zielona kropka)

---

## Ważne
- Na PC możesz wyłączyć lokalnego `python bot.py` — inaczej będą 2 boty.
- Ustawienia zapisują się na dysku Render (`/var/data`).
- Muzyka może wymagać FFmpeg — na razie skup się na AI / fact-check.

## Jak coś nie wstanie
1. Render → usługa → **Logs** (logi)
2. Skopiuj czerwony błąd i wyślij mi — pomogę

## Alternatywa (tańsza, trudniejsza)
VPS np. Hetzner / Contabo (~20–30 zł/mies.) — jeden serwer na bot+panel.
Jak wolisz tę drogę, napisz „chcę VPS” i poprowadzę krok po kroku.
