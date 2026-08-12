"""Local sanity checks before/after Render deploys."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FILES = [
    "web/app.py",
    "web/payments.py",
    "web/stripe_catalog.py",
    "web/config.py",
    "utils/plans.py",
    "utils/settings.py",
]


def main() -> None:
    for rel in FILES:
        ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        print("syntax_ok", rel)

    from web.stripe_catalog import (
        currency_from_request_headers,
        detect_checkout_currency,
        label_for,
    )

    assert detect_checkout_currency(accept_language="ru-RU") == "RUB"
    assert detect_checkout_currency(accept_language="pl-PL") == "PLN"
    assert detect_checkout_currency(accept_language="de-DE") == "EUR"
    assert detect_checkout_currency(accept_language="zh-CN") == "CNY"
    assert currency_from_request_headers({"accept-language": "pl-PL"}) == "PLN"
    assert currency_from_request_headers({"cf-ipcountry": "RU"}) == "RUB"
    assert label_for("ultra", "PLN") == "57 zł / mo"
    print("currency_ok")

    from web.app import app  # noqa: F401

    print("import_app_ok")

    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    from utils.plans import (
        FREE_FEATURES,
        PREMIUM_FEATURES,
        ULTRA_FEATURES,
        PlanInfo,
    )

    env = Environment(
        loader=FileSystemLoader(str(ROOT / "web" / "templates")),
        undefined=StrictUndefined,
    )
    template = env.get_template("guild.html")
    plan = PlanInfo(
        plan="ultra",
        active=True,
        label="Ultra Demo",
        trial_ends="2026-11-09",
        trial_days_left=88,
        is_trial=True,
        ultra_slots_used=2,
        ultra_slots_limit=10,
    )
    html = template.render(
        request=type("R", (), {"url": type("U", (), {"path": "/dashboard/1"})()})(),
        user={"username": "x"},
        guild={"id": "1", "name": "test"},
        bot_in=True,
        invite_url="x",
        language="auto",
        plan=plan,
        channels=[],
        saved=False,
        paid=False,
        canceled=False,
        switched_free=False,
        switched_premium=False,
        switched_ultra=False,
        switch_error=None,
        free_features=FREE_FEATURES,
        premium_features=PREMIUM_FEATURES,
        ultra_features=ULTRA_FEATURES,
        has_premium=True,
        payments_enabled=True,
        price_label="x",
        ultra_price_label="x",
        lifetime_price_label="x",
        paypal_url="",
        is_paid_premium=True,
        is_ultra=True,
        is_lifetime=False,
        checkout_currency="PLN",
        regional_premium_price="20 zł / mo",
        regional_ultra_price="57 zł / mo",
        regional_lifetime_price="265 zł once",
        demo_until_example="2026-11-13",
    )
    assert 'name="currency"' not in html
    assert "57 zł" in html
    print("template_ok", len(html))
    print("ALL_OK")


if __name__ == "__main__":
    main()
