"""Database models. Money is stored as integer cents; properties expose Decimals."""
from dataclasses import dataclass
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager
from .utils import cents_to_decimal

ROLE_CUSTOMER = "klant"
ROLE_ADMIN = "admin"

ORDER_STATUSES = ["Ontvangen", "In behandeling", "Verzonden"]


@dataclass(frozen=True)
class Category:
    slug: str
    label: str
    short: str
    tagline: str
    image: str


CATEGORIES = [
    Category("klassiek", "Klassieke horloges", "klassiek", "Analoog, automatisch en quartz", "img/categories/klassiek.svg"),
    Category("smartwatch", "Smartwatches & trackers", "smartwatches", "Slim, sportief en altijd verbonden", "img/categories/smartwatch.svg"),
    Category("accessoire", "Accessoires", "accessoires", "Bandjes, opladers en opbergdozen", "img/categories/accessoire.svg"),
]
CATEGORY_BY_SLUG = {c.slug: c for c in CATEGORIES}


def _utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_CUSTOMER)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)

    orders = db.relationship("Order", back_populates="user", order_by="Order.created_at.desc()")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


class Product(db.Model):
    __tablename__ = "products"
    __table_args__ = (
        db.CheckConstraint("price_cents >= 0", name="ck_product_price_positive"),
        db.CheckConstraint("stock >= 0", name="ck_product_stock_positive"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    price_cents = db.Column(db.Integer, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    category = db.Column(db.String(30), nullable=False, index=True)
    image_url = db.Column(db.String(500), nullable=False, default="")
    featured = db.Column(db.Boolean, nullable=False, default=False)
    # Products that appear in orders are hidden instead of deleted (keeps order history intact).
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)

    @property
    def price(self):
        return cents_to_decimal(self.price_cents)

    @property
    def in_stock(self) -> bool:
        return self.stock > 0

    @property
    def category_label(self) -> str:
        category = CATEGORY_BY_SLUG.get(self.category)
        return category.label if category else self.category


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    status = db.Column(db.String(30), nullable=False, default=ORDER_STATUSES[0])
    subtotal_cents = db.Column(db.Integer, nullable=False)
    shipping_cents = db.Column(db.Integer, nullable=False)
    total_cents = db.Column(db.Integer, nullable=False)
    # Shipping address, stored per order so later profile changes don't alter history.
    shipping_name = db.Column(db.String(120), nullable=False)
    shipping_street = db.Column(db.String(200), nullable=False)
    shipping_postal_code = db.Column(db.String(10), nullable=False)
    shipping_city = db.Column(db.String(100), nullable=False)

    user = db.relationship("User", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    @property
    def number(self) -> str:
        """Human-friendly order number, e.g. TS-2026-00042."""
        return f"TS-{self.created_at.year}-{self.id:05d}"

    @property
    def subtotal(self):
        return cents_to_decimal(self.subtotal_cents)

    @property
    def shipping(self):
        return cents_to_decimal(self.shipping_cents)

    @property
    def total(self):
        return cents_to_decimal(self.total_cents)


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product_name = db.Column(db.String(150), nullable=False)  # snapshot at time of order
    quantity = db.Column(db.Integer, nullable=False)
    unit_price_cents = db.Column(db.Integer, nullable=False)  # price at time of order

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")

    @property
    def unit_price(self):
        return cents_to_decimal(self.unit_price_cents)

    @property
    def line_total(self):
        return cents_to_decimal(self.unit_price_cents * self.quantity)
