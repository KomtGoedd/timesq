"""Session-based shopping cart and order placement.

The cart lives in the signed session cookie as ``{"<product_id>": quantity}``,
so it works for visitors without an account and survives logging in.
"""
from dataclasses import dataclass, field

from flask import current_app, session
from sqlalchemy import select, update

from .extensions import db
from .models import ORDER_STATUSES, Order, OrderItem, Product
from .utils import cents_to_decimal

SESSION_KEY = "cart"


# --------------------------------------------------------------------------- #
# Raw cart in the session
# --------------------------------------------------------------------------- #
def get_cart() -> dict[str, int]:
    """Return the cart, ignoring anything malformed in the session."""
    raw = session.get(SESSION_KEY)
    cart: dict[str, int] = {}
    if isinstance(raw, dict):
        for key, quantity in raw.items():
            try:
                product_id, quantity = int(key), int(quantity)
            except (TypeError, ValueError):
                continue
            if quantity > 0:
                cart[str(product_id)] = quantity
    return cart


def save_cart(cart: dict[str, int]) -> None:
    session[SESSION_KEY] = cart


def clear_cart() -> None:
    session.pop(SESSION_KEY, None)


def quantity_in_cart(product_id: int) -> int:
    return get_cart().get(str(product_id), 0)


def set_quantity(product_id: int, quantity: int) -> None:
    """Set the quantity of a product; 0 or less removes it."""
    cart = get_cart()
    if quantity > 0:
        cart[str(product_id)] = quantity
    else:
        cart.pop(str(product_id), None)
    save_cart(cart)


# --------------------------------------------------------------------------- #
# Cart with products and totals
# --------------------------------------------------------------------------- #
def shipping_cents_for(subtotal_cents: int) -> int:
    """Free shipping from the threshold (EUR 50), otherwise a flat fee (EUR 4.95)."""
    if subtotal_cents <= 0:
        return 0
    config = current_app.config
    if subtotal_cents >= config["FREE_SHIPPING_THRESHOLD_CENTS"]:
        return 0
    return config["SHIPPING_COST_CENTS"]


@dataclass
class CartLine:
    product: Product
    quantity: int

    @property
    def line_total_cents(self) -> int:
        return self.product.price_cents * self.quantity

    @property
    def line_total(self):
        return cents_to_decimal(self.line_total_cents)

    @property
    def at_max(self) -> bool:
        return self.quantity >= self.product.stock


@dataclass
class CartSummary:
    lines: list[CartLine] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)  # changes made because stock changed

    @property
    def item_count(self) -> int:
        return sum(line.quantity for line in self.lines)

    @property
    def subtotal_cents(self) -> int:
        return sum(line.line_total_cents for line in self.lines)

    @property
    def shipping_cents(self) -> int:
        return shipping_cents_for(self.subtotal_cents)

    @property
    def total_cents(self) -> int:
        return self.subtotal_cents + self.shipping_cents

    @property
    def subtotal(self):
        return cents_to_decimal(self.subtotal_cents)

    @property
    def shipping(self):
        return cents_to_decimal(self.shipping_cents)

    @property
    def total(self):
        return cents_to_decimal(self.total_cents)

    @property
    def free_shipping_remaining(self):
        """Amount still needed for free shipping (0 when already free)."""
        threshold = current_app.config["FREE_SHIPPING_THRESHOLD_CENTS"]
        return cents_to_decimal(max(threshold - self.subtotal_cents, 0))

    @property
    def free_shipping_progress(self) -> int:
        threshold = current_app.config["FREE_SHIPPING_THRESHOLD_CENTS"]
        return min(100, round(self.subtotal_cents * 100 / threshold))


def load_cart() -> CartSummary:
    """Load the cart's products and enforce the current stock.

    Products that no longer exist or are sold out are removed, and quantities
    above the available stock are lowered. Every change is reported in
    ``notices`` so the customer is never surprised at checkout.
    """
    cart = get_cart()
    if not cart:
        return CartSummary()

    ids = [int(key) for key in cart]
    products = {p.id: p for p in db.session.scalars(select(Product).where(Product.id.in_(ids)))}

    summary, cleaned = CartSummary(), {}
    for key, quantity in cart.items():
        product = products.get(int(key))
        if product is None or not product.is_active:
            summary.notices.append("Een product is niet meer leverbaar en is uit je winkelmand gehaald.")
            continue
        if product.stock <= 0:
            summary.notices.append(f"{product.name} is uitverkocht en is uit je winkelmand gehaald.")
            continue
        if quantity > product.stock:
            summary.notices.append(
                f"Van {product.name} zijn er nog {product.stock} op voorraad. We hebben het aantal aangepast."
            )
            quantity = product.stock
        cleaned[key] = quantity
        summary.lines.append(CartLine(product, quantity))

    if cleaned != cart:
        save_cart(cleaned)
    summary.lines.sort(key=lambda line: line.product.name)
    return summary


# --------------------------------------------------------------------------- #
# Checkout
# --------------------------------------------------------------------------- #
class OutOfStockError(Exception):
    """Raised when stock ran out between loading the cart and placing the order."""

    def __init__(self, product_name: str):
        super().__init__(product_name)
        self.product_name = product_name


def place_order(user, summary: CartSummary, *, name: str, street: str, postal_code: str, city: str) -> Order:
    """Create the order and lower the stock in a single transaction.

    Each stock update only succeeds while enough stock is left
    (``WHERE stock >= quantity``), so two customers can never buy the last
    item twice. If any line fails, everything is rolled back.
    """
    try:
        for line in summary.lines:
            result = db.session.execute(
                update(Product)
                .where(
                    Product.id == line.product.id,
                    Product.is_active.is_(True),
                    Product.stock >= line.quantity,
                )
                .values(stock=Product.stock - line.quantity)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise OutOfStockError(line.product.name)

        order = Order(
            user_id=user.id,
            status=ORDER_STATUSES[0],
            subtotal_cents=summary.subtotal_cents,
            shipping_cents=summary.shipping_cents,
            total_cents=summary.total_cents,
            shipping_name=name,
            shipping_street=street,
            shipping_postal_code=postal_code,
            shipping_city=city,
        )
        for line in summary.lines:
            order.items.append(
                OrderItem(
                    product_id=line.product.id,
                    product_name=line.product.name,
                    quantity=line.quantity,
                    unit_price_cents=line.product.price_cents,
                )
            )
        db.session.add(order)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return order
