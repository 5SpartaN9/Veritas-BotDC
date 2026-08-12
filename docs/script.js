const reveals = document.querySelectorAll(".reveal");

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.16 }
);

reveals.forEach((el) => observer.observe(el));

function scrollToHash(hash) {
  if (!hash || hash === "#") return;
  const id = decodeURIComponent(hash.slice(1));
  const target = document.getElementById(id);
  if (!target) return;
  target.scrollIntoView({ behavior: "smooth", block: "start" });
}

document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener("click", (event) => {
    const href = link.getAttribute("href");
    if (!href || href === "#") return;
    const target = document.getElementById(decodeURIComponent(href.slice(1)));
    if (!target) return;
    event.preventDefault();
    history.pushState(null, "", href);
    scrollToHash(href);
  });
});

window.addEventListener("hashchange", () => scrollToHash(location.hash));

/* --- Regional pricing estimates (checkout = billing/card country) --- */
const BASE = { premium: 5.99, ultra: 16.99, lifetime: 79 };
const MIN_FACTOR = 0.48;

const REGIONS = {
  US: { name: "United States", currency: "USD", symbol: "$", factor: 1.0, fx: 1 },
  CA: { name: "Canada", currency: "CAD", symbol: "C$", factor: 0.95, fx: 1.37 },
  GB: { name: "United Kingdom", currency: "GBP", symbol: "£", factor: 0.95, fx: 0.79 },
  IE: { name: "Ireland", currency: "EUR", symbol: "€", factor: 0.95, fx: 0.92 },
  DE: { name: "Germany", currency: "EUR", symbol: "€", factor: 0.92, fx: 0.92 },
  FR: { name: "France", currency: "EUR", symbol: "€", factor: 0.9, fx: 0.92 },
  NL: { name: "Netherlands", currency: "EUR", symbol: "€", factor: 0.94, fx: 0.92 },
  SE: { name: "Sweden", currency: "SEK", symbol: "kr", factor: 0.92, fx: 10.5 },
  NO: { name: "Norway", currency: "NOK", symbol: "kr", factor: 1.05, fx: 10.7 },
  CH: { name: "Switzerland", currency: "CHF", symbol: "CHF", factor: 1.1, fx: 0.88 },
  AU: { name: "Australia", currency: "AUD", symbol: "A$", factor: 0.95, fx: 1.53 },
  NZ: { name: "New Zealand", currency: "NZD", symbol: "NZ$", factor: 0.9, fx: 1.66 },
  JP: { name: "Japan", currency: "JPY", symbol: "¥", factor: 0.88, fx: 150 },
  KR: { name: "South Korea", currency: "KRW", symbol: "₩", factor: 0.85, fx: 1350 },
  SG: { name: "Singapore", currency: "SGD", symbol: "S$", factor: 0.95, fx: 1.34 },
  AE: { name: "United Arab Emirates", currency: "AED", symbol: "AED", factor: 0.92, fx: 3.67 },
  PL: { name: "Poland", currency: "PLN", symbol: "zł", factor: 0.85, fx: 3.95 },
  CZ: { name: "Czechia", currency: "CZK", symbol: "Kč", factor: 0.82, fx: 23 },
  HU: { name: "Hungary", currency: "HUF", symbol: "Ft", factor: 0.72, fx: 360 },
  RO: { name: "Romania", currency: "RON", symbol: "lei", factor: 0.68, fx: 4.6 },
  ES: { name: "Spain", currency: "EUR", symbol: "€", factor: 0.85, fx: 0.92 },
  IT: { name: "Italy", currency: "EUR", symbol: "€", factor: 0.85, fx: 0.92 },
  PT: { name: "Portugal", currency: "EUR", symbol: "€", factor: 0.8, fx: 0.92 },
  GR: { name: "Greece", currency: "EUR", symbol: "€", factor: 0.75, fx: 0.92 },
  TR: { name: "Türkiye", currency: "TRY", symbol: "₺", factor: 0.55, fx: 34 },
  UA: { name: "Ukraine", currency: "UAH", symbol: "₴", factor: 0.5, fx: 41 },
  RU: { name: "Russia", currency: "RUB", symbol: "₽", factor: 0.52, fx: 92 },
  CN: { name: "China", currency: "CNY", symbol: "¥", factor: 0.55, fx: 7.25 },
  TW: { name: "Taiwan", currency: "TWD", symbol: "NT$", factor: 0.75, fx: 32 },
  HK: { name: "Hong Kong", currency: "HKD", symbol: "HK$", factor: 0.9, fx: 7.8 },
  IR: { name: "Iran", currency: "IRR", symbol: "﷼", factor: 0.48, fx: 42000 },
  SA: { name: "Saudi Arabia", currency: "SAR", symbol: "SAR", factor: 0.7, fx: 3.75 },
  IL: { name: "Israel", currency: "ILS", symbol: "₪", factor: 0.9, fx: 3.7 },
  KZ: { name: "Kazakhstan", currency: "KZT", symbol: "₸", factor: 0.48, fx: 480 },
  PK: { name: "Pakistan", currency: "PKR", symbol: "Rs", factor: 0.48, fx: 278 },
  BR: { name: "Brazil", currency: "BRL", symbol: "R$", factor: 0.58, fx: 5.5 },
  MX: { name: "Mexico", currency: "MXN", symbol: "MX$", factor: 0.55, fx: 17.5 },
  AR: { name: "Argentina", currency: "ARS", symbol: "AR$", factor: 0.5, fx: 950 },
  CL: { name: "Chile", currency: "CLP", symbol: "CLP", factor: 0.62, fx: 950 },
  IN: { name: "India", currency: "INR", symbol: "₹", factor: 0.48, fx: 84 },
  PH: { name: "Philippines", currency: "PHP", symbol: "₱", factor: 0.5, fx: 58 },
  ID: { name: "Indonesia", currency: "IDR", symbol: "Rp", factor: 0.48, fx: 16000 },
  VN: { name: "Vietnam", currency: "VND", symbol: "₫", factor: 0.48, fx: 25000 },
  TH: { name: "Thailand", currency: "THB", symbol: "฿", factor: 0.55, fx: 35 },
  MY: { name: "Malaysia", currency: "MYR", symbol: "RM", factor: 0.62, fx: 4.5 },
  ZA: { name: "South Africa", currency: "ZAR", symbol: "R", factor: 0.55, fx: 18.5 },
  NG: { name: "Nigeria", currency: "NGN", symbol: "₦", factor: 0.48, fx: 1550 },
  EG: { name: "Egypt", currency: "EGP", symbol: "E£", factor: 0.48, fx: 48 },
};

const ZERO_DECIMAL = new Set(["JPY", "KRW", "VND", "IDR", "HUF", "CLP", "ARS", "NGN", "IRR", "KZT", "PKR"]);

function niceRound(amount, currency) {
  if (ZERO_DECIMAL.has(currency)) {
    if (amount >= 10000) return Math.round(amount / 1000) * 1000;
    if (amount >= 1000) return Math.round(amount / 100) * 100;
    return Math.round(amount / 10) * 10;
  }
  if (amount >= 100) return Math.round(amount);
  if (amount >= 20) return Math.round(amount * 2) / 2;
  const whole = Math.floor(amount);
  if (whole < 1) return Math.round(amount * 100) / 100;
  return whole + 0.99;
}

function formatMoney(amount, region) {
  const { currency, symbol } = region;
  if (ZERO_DECIMAL.has(currency)) {
    const n = Math.round(amount).toLocaleString("en-US").replace(/,/g, " ");
    if (currency === "JPY") return `¥${n}`;
    if (currency === "KRW") return `₩${n}`;
    if (currency === "VND") return `${n}₫`;
    if (currency === "IDR") return `Rp ${n}`;
    if (currency === "HUF") return `${n} Ft`;
    if (currency === "CLP") return `CLP ${n}`;
    if (currency === "ARS") return `AR$ ${n}`;
    if (currency === "IRR") return `${n} ﷼`;
    if (currency === "KZT") return `${n} ₸`;
    if (currency === "PKR") return `Rs ${n}`;
    return `₦${n}`;
  }
  const fixed = amount.toFixed(2);
  if (currency === "PLN") return `${fixed.replace(".", ",")} zł`;
  if (currency === "EUR") return `€${fixed}`;
  if (currency === "GBP") return `£${fixed}`;
  if (currency === "USD") return `$${fixed}`;
  if (currency === "RUB") return `${Math.round(amount)} ₽`;
  if (currency === "CNY") return `¥${fixed}`;
  if (currency === "ILS") return `₪${fixed}`;
  if (currency === "SAR") return `${fixed} SAR`;
  if (currency === "TWD") return `NT$${Math.round(amount)}`;
  if (currency === "HKD") return `HK$${fixed}`;
  if (["$", "C$", "A$", "NZ$", "MX$", "S$", "R$"].includes(symbol)) {
    return `${symbol}${fixed}`;
  }
  return `${fixed} ${symbol}`;
}

function localAmount(baseUsd, region) {
  const factor = Math.max(region.factor, MIN_FACTOR);
  return niceRound(baseUsd * factor * region.fx, region.currency);
}

function guessRegionCode() {
  const lang = (navigator.language || "en-US").toUpperCase();
  const parts = lang.split("-");
  const region = parts[1] || parts[0];
  if (REGIONS[region]) return region;
  const byLang = {
    PL: "PL",
    DE: "DE",
    FR: "FR",
    ES: "ES",
    PT: "PT",
    IT: "IT",
    JA: "JP",
    KO: "KR",
    UK: "UA",
    RU: "RU",
    ZH: "CN",
    FA: "IR",
    TR: "TR",
    HI: "IN",
    TH: "TH",
    VI: "VN",
    ID: "ID",
    AR: "EG",
    HE: "IL",
  };
  if (byLang[parts[0]]) return byLang[parts[0]];
  return "US";
}

function applyPrices(code) {
  const region = REGIONS[code] || REGIONS.US;
  const premium = localAmount(BASE.premium, region);
  const ultra = localAmount(BASE.ultra, region);
  const lifetime = localAmount(BASE.lifetime, region);

  const nameEl = document.getElementById("price-region-name");
  if (nameEl) nameEl.textContent = region.name;

  document.querySelectorAll('[data-price="premium"]').forEach((el) => {
    el.textContent = `${formatMoney(premium, region)} / mo`;
  });
  document.querySelectorAll('[data-price="ultra"]').forEach((el) => {
    el.textContent = `${formatMoney(ultra, region)} / mo`;
  });
  document.querySelectorAll('[data-price="lifetime"]').forEach((el) => {
    el.textContent = `${formatMoney(lifetime, region)} once`;
  });
  document.querySelectorAll('[data-price="ref-premium"]').forEach((el) => {
    el.textContent = `$${BASE.premium.toFixed(2)}`;
  });
  document.querySelectorAll('[data-price="ref-ultra"]').forEach((el) => {
    el.textContent = `$${BASE.ultra.toFixed(2)}`;
  });
  document.querySelectorAll('[data-price="ref-lifetime"]').forEach((el) => {
    el.textContent = `$${BASE.lifetime.toFixed(0)}`;
  });
}

function initRegionalPricing() {
  // Auto-detect only — no country picker (VPN shopping).
  // Real charge must use Stripe billing / card country.
  applyPrices(guessRegionCode());
}

initRegionalPricing();

/* --- Early demo end date (today + 3 calendar months) --- */
function addCalendarMonths(date, months) {
  const out = new Date(date.getTime());
  const day = out.getDate();
  out.setMonth(out.getMonth() + months);
  if (out.getDate() < day) out.setDate(0); // clamp end-of-month
  return out;
}

function formatDemoUntil(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function initDemoUntilLabels() {
  const until = formatDemoUntil(addCalendarMonths(new Date(), 3));
  document.querySelectorAll("[data-demo-until]").forEach((el) => {
    el.textContent = until;
  });
}

initDemoUntilLabels();

/* --- Reviews (stored on Render API) --- */
const REVIEWS_API =
  location.hostname.includes("onrender.com") || location.hostname === "127.0.0.1"
    ? "/api/reviews"
    : "https://veritas-zx7p.onrender.com/api/reviews";

function starsHtml(n) {
  const filled = Math.max(0, Math.min(5, Number(n) || 0));
  return "★".repeat(filled) + "☆".repeat(5 - filled);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderReviews(payload) {
  const list = document.getElementById("reviews-list");
  const summary = document.getElementById("reviews-summary");
  if (!list) return;

  const rows = payload.reviews || [];
  if (summary) {
    if (payload.count > 0 && payload.average != null) {
      summary.hidden = false;
      summary.textContent = `${payload.average} / 5 average · ${payload.count} review${
        payload.count === 1 ? "" : "s"
      }`;
    } else {
      summary.hidden = true;
    }
  }

  if (!rows.length) {
    list.innerHTML = `<p class="muted">No reviews yet — be the first.</p>`;
    return;
  }

  list.innerHTML = rows
    .map(
      (r) => `
      <article class="review-item">
        <div class="review-item-top">
          <strong>${escapeHtml(r.name)}</strong>
          <span class="review-stars" aria-label="${r.stars} out of 5 stars">${starsHtml(
            r.stars
          )}</span>
        </div>
        <p>${escapeHtml(r.text)}</p>
      </article>`
    )
    .join("");
}

async function loadReviews() {
  const list = document.getElementById("reviews-list");
  if (!list) return;
  try {
    const res = await fetch(REVIEWS_API, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    renderReviews(await res.json());
  } catch (err) {
    list.innerHTML = `<p class="muted">Reviews are temporarily unavailable.</p>`;
  }
}

function setStarSelection(value) {
  const hidden = document.getElementById("review-stars");
  const buttons = document.querySelectorAll(".star-btn");
  if (hidden) hidden.value = String(value);
  buttons.forEach((btn) => {
    const n = Number(btn.dataset.stars);
    btn.classList.toggle("on", n <= value);
    btn.setAttribute("aria-checked", n === value ? "true" : "false");
  });
}

function initReviewForm() {
  const form = document.getElementById("review-form");
  if (!form) return;

  setStarSelection(5);
  document.querySelectorAll(".star-btn").forEach((btn) => {
    btn.addEventListener("click", () => setStarSelection(Number(btn.dataset.stars)));
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("review-status");
    const name = document.getElementById("review-name")?.value || "";
    const stars = Number(document.getElementById("review-stars")?.value || 0);
    const text = document.getElementById("review-text")?.value || "";
    const submitBtn = form.querySelector('button[type="submit"]');

    if (status) {
      status.className = "review-status";
      status.textContent = "Sending…";
    }
    if (submitBtn) submitBtn.disabled = true;

    try {
      const res = await fetch(REVIEWS_API, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ name, stars, text }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `Could not post (${res.status})`);
      }
      form.reset();
      setStarSelection(5);
      if (status) {
        status.className = "review-status ok";
        status.textContent = "Thanks — your review is live.";
      }
      await loadReviews();
    } catch (err) {
      if (status) {
        status.className = "review-status err";
        status.textContent = err.message || "Could not post review.";
      }
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });
}

initReviewForm();
loadReviews();
