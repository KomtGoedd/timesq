"""Small helpers: money and date formatting, template filters and globals."""
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import request, session, url_for

CENT = Decimal("0.01")

try:
    LOCAL_TZ = ZoneInfo("Europe/Amsterdam")
except ZoneInfoNotFoundError:  # no tz database installed (pip install tzdata)
    LOCAL_TZ = timezone.utc

MONTHS = [
    "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
]


def format_date(value: datetime, with_time: bool = False) -> str:
    """Dutch date in Amsterdam time: '27 november 2026' (optionally ', 14:05')."""
    if value is None:
        return ""
    if value.tzinfo is None:  # SQLite returns naive datetimes; we store UTC
        value = value.replace(tzinfo=timezone.utc)
    local = value.astimezone(LOCAL_TZ)
    text = f"{local.day} {MONTHS[local.month - 1]} {local.year}"
    return f"{text}, {local:%H:%M}" if with_time else text


def cents_to_decimal(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(CENT)


def decimal_to_cents(amount) -> int:
    return int((Decimal(amount) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_euro(amount) -> str:
    """Format an amount in Dutch notation: Decimal('1234.5') -> '€ 1.234,50'."""
    value = Decimal(amount).quantize(CENT, rounding=ROUND_HALF_UP)
    text = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"€ {text}"


def image_src(path: str) -> str:
    """Resolve a stored image path: absolute URLs pass through, others live in /static."""
    if not path:
        return url_for("static", filename="img/icon.svg")
    if path.startswith(("http://", "https://", "/")):
        return path
    return url_for("static", filename=path)


def url_with(**changes) -> str:
    """URL of the current page with some query parameters changed.

    A value of None or "" removes that parameter. Used by the filter chips so
    choosing a category keeps the current search, sort and price filter.
    """
    args = request.args.to_dict()
    for key, value in changes.items():
        if value in (None, ""):
            args.pop(key, None)
        else:
            args[key] = value
    return url_for(request.endpoint, **(request.view_args or {}), **args)


def _active_tab() -> str:
    """Which tab of the app navigation should be highlighted for this request."""
    endpoint = request.endpoint or ""
    if endpoint == "shop.home":
        return "home"
    section = endpoint.split(".")[0]
    if section == "shop":
        return "shop"
    if section == "cart":
        return "cart"
    if section in {"auth", "account", "admin"}:
        return "account"
    return ""


def _cart_count() -> int:
    cart = session.get("cart") or {}
    try:
        return sum(int(qty) for qty in cart.values())
    except (TypeError, ValueError):
        return 0


def register_template_helpers(app) -> None:
    app.add_template_filter(format_euro, "euro")
    app.add_template_filter(image_src, "image_src")
    app.add_template_global(url_with, "url_with")
    app.add_template_filter(format_date, "datum")

    @app.context_processor
    def inject_globals():
        from .models import CATEGORIES, ORDER_STATUSES

        return {
            "categories": CATEGORIES,
            "order_statuses": ORDER_STATUSES,
            "cart_count": _cart_count(),
            "active_tab": _active_tab(),
            "current_year": datetime.now().year,
        }
