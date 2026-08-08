# Deploy & payments

## Public website (GitHub Pages)

Landing page lives in `website/`. After you push to `main`, GitHub Actions
deploys it to GitHub Pages.

1. Repo → **Settings → Pages → Source: GitHub Actions**
2. Push to `main` (or run the **Deploy website** workflow)
3. URL looks like: `https://YOUR_USER.github.io/Veritas-BotDC/`

If the site is in a subpath, open `website/index.html` and keep asset paths
relative (`styles.css`, `assets/...`) — they already are.

## Dashboard + payments (Render / any VPS)

The FastAPI panel cannot run on GitHub Pages. Use [Render](https://render.com)
(`render.yaml` included) or a VPS:

1. Connect this GitHub repo to Render → **New → Blueprint**
2. Set env vars from `.env.example` (especially Discord + Stripe)
3. Set:
   - `PUBLIC_BASE_URL=https://your-app.onrender.com`
   - `DISCORD_REDIRECT_URI=https://your-app.onrender.com/auth/callback`
4. In Discord Developer Portal → OAuth2 → Redirects, add the same callback URL

### Stripe (card / BLIK / optional PayPal)

1. Create account: https://dashboard.stripe.com/register
2. **Product** → Premium → recurring price (e.g. $4.99/month) → copy `price_...`
3. Copy **Secret key** + **Publishable key** into env
4. Developers → **Webhooks** → endpoint:
   `https://your-app.onrender.com/webhooks/stripe`
   Events: `checkout.session.completed`, `customer.subscription.updated`,
   `customer.subscription.deleted`, `invoice.payment_failed`
5. Copy webhook signing secret → `STRIPE_WEBHOOK_SECRET`
6. In Stripe → Settings → Payment methods: enable **Card**, and optionally
   **PayPal** / local methods (BLIK where available)

Checkout starts from the server page in the dashboard:
**Upgrade with Stripe**.

### PayPal (manual link)

If you prefer PayPal.me without Stripe:

1. Create https://paypal.me/YourName
2. Set `PAYPAL_ME_URL=https://paypal.me/YourName/4.99`
3. After payment, turn Premium on manually:
   ```python
   from utils.settings import settings_store
   settings_store.set_premium(GUILD_ID, True)
   ```

For automatic unlocks, use Stripe (with PayPal enabled inside Stripe).
