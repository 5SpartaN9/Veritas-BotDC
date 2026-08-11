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

---

## Krok 3b — Płatności Stripe (Premium / Ultra / Lifetime)

### A. Konto i klucze
1. Załóż / zaloguj: https://dashboard.stripe.com
2. Na start możesz zostać w trybie **Test** (przełącznik „Test mode”).
3. **Developers** → **API keys**:
   - `Secret key` (`sk_test_…` albo później `sk_live_…`) → `STRIPE_SECRET_KEY`
   - `Publishable key` (`pk_test_…` / `pk_live_…`) → `STRIPE_PUBLISHABLE_KEY`

### B. Trzy ceny (Products)
Wejdź **Product catalog** → **Add product** i zrób 3 produkty:

| Produkt | Typ ceny | Kwota US (lista) | Env na Render |
|---------|----------|------------------|---------------|
| Veritas Premium | **Recurring** / month | **$5.99** | `STRIPE_PRICE_ID` |
| Veritas Ultra | **Recurring** / month | **$16.99** | `STRIPE_PRICE_ID_ULTRA` |
| Veritas Ultra Lifetime | **One-time** | **$79** | `STRIPE_PRICE_ID_ULTRA_LIFETIME` |

Po utworzeniu skopiuj **Price ID** (`price_…`), nie Product ID.

Regionalne ceny (PLN, EUR…) Stripe może doliczyć Adaptive Pricing / lokalne Prices później.
Na start wystarczy USD — checkout i tak działa międzynarodowo.

### C. Webhook (żeby po płatności włączył się plan)
1. **Developers** → **Webhooks** → **Add endpoint**
2. URL:
   `https://veritas-zx7p.onrender.com/webhooks/stripe`
   (jeśli masz inny adres Render — wstaw swój)
3. Zaznacz eventy:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
4. Otwórz endpoint → **Signing secret** (`whsec_…`) → `STRIPE_WEBHOOK_SECRET`

### D. Wpisz na Render (Environment)
W usłudze **veritas** dodaj / uzupełnij:

- `STRIPE_SECRET_KEY`
- `STRIPE_PUBLISHABLE_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_ID`
- `STRIPE_PRICE_ID_ULTRA`
- `STRIPE_PRICE_ID_ULTRA_LIFETIME`
- (opcjonalnie etykiety)
  - `PREMIUM_PRICE_LABEL` = `$5.99 / month`
  - `ULTRA_PRICE_LABEL` = `$16.99 / month`
  - `ULTRA_LIFETIME_PRICE_LABEL` = `$79 once · forever`

Zapisz → poczekaj na redeploy (**Live**).

### E. Customer Portal (anulowanie subskrypcji)
1. Stripe → **Settings** → **Billing** → **Customer portal**
2. Włącz portal (cancel / update payment method)
3. Zapisz

### F. Test
1. Wejdź na panel: `https://veritas-zx7p.onrender.com/dashboard`
2. Zaloguj Discord → wybierz serwer
3. Kliknij **Get Premium** / **Get Ultra** / **Ultra Lifetime**
4. W **Test mode** użyj karty: `4242 4242 4242 4242`, dowolna przyszła data, dowolne CVC
5. Po powrocie plan powinien być **Active** (webhook)
6. Jak nie — Render → **Logs** + Stripe → Webhook → **Attempts**

### G. Na prawdziwe pieniądze
1. Wyłącz **Test mode**
2. Utwórz te same 3 Prices w trybie **Live** (albo aktywuj konto i skopiuj live keys)
3. Podmień na Render wszystkie `sk_live_`, `pk_live_`, `whsec_` i `price_…` z Live
4. Webhook URL ten sam, ale osobny endpoint w Live mode

Stripe (płatności) — szczegóły powyżej.

### Multi-currency prices (USD / EUR / PLN / RUB / CNY)

Dla każdego produktu dodaj **osobną cenę** w każdej walucie
(Product → Add another price). Kwoty:

| Plan | USD | EUR | PLN | RUB | CNY |
|------|-----|-----|-----|-----|-----|
| Premium / mo | 5.99 | 5.49 | 20 | 290 | 24 |
| Ultra / mo | 16.99 | 14.99 | 57 | 820 | 68 |
| Lifetime once | 79 | 69 | 265 | 3800 | 315 |

Na Render Environment wklej `price_…` np.:
`STRIPE_PRICE_ULTRA_PLN`, `STRIPE_PRICE_PREMIUM_EUR`, …
Stare `STRIPE_PRICE_ID` / `_ULTRA` / `_ULTRA_LIFETIME` = fallback USD.

W panelu przy kupnie jest wybór waluty — klient płaci **dokładnie** tę kwotę.

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
