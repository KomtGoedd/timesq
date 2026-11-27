"""HTTP routes, grouped in blueprints per area of the shop.

shop     homepage, product overview and detail pages      (stories 1-3)
cart     cart, checkout and order confirmation              (stories 4, 6)
auth     register, log in, log out                          (story 5)
account  account page and the customer's own orders         (story 7)
admin    product and order management, admins only          (stories 8-9)
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from . import cart as shop_cart
from .extensions import db
from .forms import CheckoutForm, LoginForm, ProductForm, RegisterForm
from .models import CATEGORY_BY_SLUG, ORDER_STATUSES, ROLE_CUSTOMER, Order, OrderItem, Product, User
from .utils import decimal_to_cents

shop_bp = Blueprint("shop", __name__)
cart_bp = Blueprint("cart", __name__)
auth_bp = Blueprint("auth", __name__)
account_bp = Blueprint("account", __name__, url_prefix="/account")
admin_bp = Blueprint("admin", __name__, url_prefix="/beheer")


def register_blueprints(app) -> None:
    for blueprint in (shop_bp, cart_bp, auth_bp, account_bp, admin_bp):
        app.register_blueprint(blueprint)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _safe_next(target: str | None) -> str | None:
    """Only allow redirects to paths on this site (prevents open redirects)."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return None


def _first_name(user: User) -> str:
    return user.name.split()[0] if user.name else ""


def _active_product_or_404(product_id: int) -> Product:
    product = db.session.get(Product, product_id)
    if product is None or not product.is_active:
        abort(404)
    return product


def _own_order_or_404(order_id: int) -> Order:
    """Customers can only see their own orders; others get a 404 (not a 403)."""
    order = db.session.get(Order, order_id)
    if order is None or order.user_id != current_user.id:
        abort(404)
    return order


# =========================================================================== #
# Shop (stories 1-3)
# =========================================================================== #
@shop_bp.route("/")
def home():
    featured = db.session.scalars(
        select(Product)
        .where(Product.is_active.is_(True), Product.featured.is_(True))
        .order_by(Product.id)
        .limit(4)
    ).all()
    return render_template("shop/home.html", featured=featured)


# Sort options for the product grid: key -> (label, ORDER BY clauses).
SORT_OPTIONS = {
    "aanbevolen": ("Aanbevolen", (Product.featured.desc(), Product.id)),
    "prijs-laag": ("Prijs: laag naar hoog", (Product.price_cents.asc(), Product.id)),
    "prijs-hoog": ("Prijs: hoog naar laag", (Product.price_cents.desc(), Product.id)),
}

# Price filters: key -> (label, minimum cents inclusive, maximum cents exclusive).
PRICE_RANGES = {
    "tot-50": ("Tot € 50", None, 5000),
    "50-200": ("€ 50 – € 200", 5000, 20000),
    "vanaf-200": ("€ 200 en meer", 20000, None),
}

MAX_SEARCH_LENGTH = 100

# From this stock level and below the detail page shows "Nog maar X op voorraad".
LOW_STOCK_THRESHOLD = 5


def _escape_like(text: str) -> str:
    """Escape LIKE wildcards so a search for '50%' matches literally."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@shop_bp.route("/producten")
def products():
    category = request.args.get("categorie", "").strip()
    price = request.args.get("prijs", "").strip()
    sort = request.args.get("sort", "aanbevolen").strip()
    search = request.args.get("q", "").strip()[:MAX_SEARCH_LENGTH]

    # Unknown values (e.g. from a hand-edited URL) are ignored with a notice.
    if category and category not in CATEGORY_BY_SLUG:
        flash("Onbekende categorie, we tonen alle producten.", "info")
        category = ""
    if price and price not in PRICE_RANGES:
        flash("Onbekend prijsfilter, dit filter is genegeerd.", "info")
        price = ""
    if sort not in SORT_OPTIONS:
        sort = "aanbevolen"

    stmt = select(Product).where(Product.is_active.is_(True))
    if category:
        stmt = stmt.where(Product.category == category)
    if price:
        _label, minimum, maximum = PRICE_RANGES[price]
        if minimum is not None:
            stmt = stmt.where(Product.price_cents >= minimum)
        if maximum is not None:
            stmt = stmt.where(Product.price_cents < maximum)
    if search:
        stmt = stmt.where(Product.name.ilike(f"%{_escape_like(search)}%", escape="\\"))
    stmt = stmt.order_by(*SORT_OPTIONS[sort][1])

    return render_template(
        "shop/products.html",
        products=db.session.scalars(stmt).all(),
        active_category=CATEGORY_BY_SLUG.get(category),
        category=category,
        price=price,
        sort=sort,
        search=search,
        sort_options=SORT_OPTIONS,
        price_ranges=PRICE_RANGES,
        max_search_length=MAX_SEARCH_LENGTH,
    )


@shop_bp.route("/product/<int:product_id>")
def product_detail(product_id: int):
    product = _active_product_or_404(product_id)

    # "More from this category": in-stock items first, then featured.
    related = db.session.scalars(
        select(Product)
        .where(
            Product.is_active.is_(True),
            Product.category == product.category,
            Product.id != product.id,
        )
        .order_by((Product.stock > 0).desc(), Product.featured.desc(), Product.id)
        .limit(4)
    ).all()
    return render_template(
        "shop/product_detail.html",
        product=product,
        related=related,
        category=CATEGORY_BY_SLUG.get(product.category),
        low_stock_threshold=LOW_STOCK_THRESHOLD,
        in_cart=shop_cart.quantity_in_cart(product.id),
    )


# =========================================================================== #
# Cart (story 4)
# =========================================================================== #
def _parse_quantity(raw) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


@cart_bp.route("/winkelmand")
def view_cart():
    summary = shop_cart.load_cart()
    for notice in summary.notices:
        flash(notice, "info")
    return render_template("cart/cart.html", summary=summary)


@cart_bp.post("/winkelmand/toevoegen/<int:product_id>")
def add(product_id: int):
    product = _active_product_or_404(product_id)
    back = url_for("shop.product_detail", product_id=product.id)

    quantity = _parse_quantity(request.form.get("aantal", 1))
    if quantity is None or quantity < 1:
        flash("Kies een geldig aantal (minimaal 1).", "error")
        return redirect(back)
    if not product.in_stock:
        flash(f"{product.name} is helaas niet op voorraad.", "error")
        return redirect(back)

    # Never more in the cart than there is in stock.
    in_cart = shop_cart.quantity_in_cart(product.id)
    new_quantity = min(in_cart + quantity, product.stock)
    if new_quantity == in_cart:
        flash(f"Je hebt alle {product.stock} beschikbare stuks al in je winkelmand.", "info")
        return redirect(back)

    shop_cart.set_quantity(product.id, new_quantity)
    added = new_quantity - in_cart
    if added < quantity:
        flash(f"Er zijn nog maar {product.stock} op voorraad. We hebben er {added} toegevoegd.", "info")
    else:
        flash(f"{added}× {product.name} toegevoegd aan je winkelmand.", "success")
    return redirect(back)


@cart_bp.post("/winkelmand/bijwerken/<int:product_id>")
def update(product_id: int):
    cart_url = url_for("cart.view_cart")
    quantity = _parse_quantity(request.form.get("aantal"))
    if quantity is None or quantity < 0:
        flash("Ongeldig aantal.", "error")
        return redirect(cart_url)

    product = db.session.get(Product, product_id)
    if quantity == 0 or product is None or not product.is_active:
        shop_cart.set_quantity(product_id, 0)
        flash("Product verwijderd uit je winkelmand.", "info")
        return redirect(cart_url)

    if quantity > product.stock:
        quantity = product.stock
        flash(f"Er zijn nog maar {product.stock} stuks van {product.name} op voorraad.", "info")
    shop_cart.set_quantity(product_id, quantity)
    return redirect(cart_url)


@cart_bp.post("/winkelmand/verwijderen/<int:product_id>")
def remove(product_id: int):
    shop_cart.set_quantity(product_id, 0)
    flash("Product verwijderd uit je winkelmand.", "info")
    return redirect(url_for("cart.view_cart"))


# =========================================================================== #
# Checkout (story 6)
# =========================================================================== #
@cart_bp.route("/afrekenen", methods=["GET", "POST"])
@login_required
def checkout():
    summary = shop_cart.load_cart()
    if summary.notices:
        # Stock changed since the customer last saw the cart: let them review first.
        for notice in summary.notices:
            flash(notice, "info")
        return redirect(url_for("cart.view_cart"))
    if not summary.lines:
        flash("Je winkelmand is leeg.", "info")
        return redirect(url_for("cart.view_cart"))

    form = CheckoutForm()
    if request.method == "GET":
        # Prefill with the account name and the address of the previous order.
        form.name.data = current_user.name
        previous = current_user.orders[0] if current_user.orders else None
        if previous:
            form.street.data = previous.shipping_street
            form.postal_code.data = previous.shipping_postal_code
            form.city.data = previous.shipping_city

    if form.validate_on_submit():
        try:
            order = shop_cart.place_order(
                current_user,
                summary,
                name=form.name.data,
                street=form.street.data,
                postal_code=form.postal_code.data,
                city=form.city.data,
            )
        except shop_cart.OutOfStockError as error:
            flash(f"Helaas, {error.product_name} is net uitverkocht geraakt. Controleer je winkelmand.", "error")
            return redirect(url_for("cart.view_cart"))

        shop_cart.clear_cart()
        flash("Betaling geslaagd! Bedankt voor je bestelling.", "success")
        return redirect(url_for("cart.confirmation", order_id=order.id))

    if form.errors:
        flash("Controleer de gemarkeerde velden.", "error")
    return render_template("cart/checkout.html", form=form, summary=summary)


@cart_bp.route("/bestelling/<int:order_id>/bevestiging")
@login_required
def confirmation(order_id: int):
    return render_template("cart/confirmation.html", order=_own_order_or_404(order_id))


# =========================================================================== #
# Accounts (story 5)
# =========================================================================== #
@auth_bp.route("/registreren", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("account.overview"))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(name=form.name.data, email=form.email.data, role=ROLE_CUSTOMER)
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:  # same e-mail registered at the same moment
            db.session.rollback()
            form.email.errors.append("Er bestaat al een account met dit e-mailadres.")
        else:
            login_user(user)
            flash(f"Welkom bij Time Square, {_first_name(user)}! Je account is aangemaakt.", "success")
            return redirect(_safe_next(request.args.get("next")) or url_for("account.overview"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/inloggen", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("account.overview"))

    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(select(User).where(User.email == form.email.data))
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash(f"Welkom terug, {_first_name(user)}!", "success")
            return redirect(_safe_next(request.args.get("next")) or url_for("account.overview"))
        # Same message for unknown e-mail and wrong password (don't reveal accounts).
        flash("Dit e-mailadres en wachtwoord horen niet bij elkaar.", "error")
    return render_template("auth/login.html", form=form)


@auth_bp.post("/uitloggen")
@login_required
def logout():
    logout_user()
    flash("Je bent uitgelogd. Tot ziens!", "info")
    return redirect(url_for("shop.home"))


# =========================================================================== #
# My account and orders (story 7)
# =========================================================================== #
@account_bp.route("/")
@login_required
def overview():
    return render_template("account/overview.html")


@account_bp.route("/bestellingen")
@login_required
def orders():
    return render_template("account/orders.html", orders=current_user.orders)


@account_bp.route("/bestellingen/<int:order_id>")
@login_required
def order_detail(order_id: int):
    return render_template("account/order_detail.html", order=_own_order_or_404(order_id))


# =========================================================================== #
# Admin (stories 8-9)
# =========================================================================== #
@admin_bp.before_request
@login_required
def require_admin():
    """Every admin page: log in first, and only users with the admin role get in."""
    if not current_user.is_admin:
        abort(403)


@admin_bp.route("/")
def index():
    return redirect(url_for("admin.orders"))


# ---- Products (story 8) ------------------------------------------------------
@admin_bp.route("/producten")
def products():
    items = db.session.scalars(
        select(Product).order_by(Product.is_active.desc(), Product.category, Product.name)
    ).all()
    return render_template("admin/products.html", products=items, low_stock_threshold=LOW_STOCK_THRESHOLD)


def _apply_product_form(product: Product, form: ProductForm) -> None:
    product.name = form.name.data
    product.description = form.description.data
    product.price_cents = decimal_to_cents(form.price.data)
    product.stock = form.stock.data
    product.category = form.category.data
    # No image given: use the illustration of the category.
    product.image_url = form.image_url.data or CATEGORY_BY_SLUG[form.category.data].image
    product.is_active = form.is_active.data
    product.featured = form.featured.data and form.is_active.data


@admin_bp.route("/producten/nieuw", methods=["GET", "POST"])
def product_create():
    form = ProductForm()
    if form.validate_on_submit():
        product = Product()
        _apply_product_form(product, form)
        db.session.add(product)
        db.session.commit()
        flash(f"Product '{product.name}' is toegevoegd.", "success")
        return redirect(url_for("admin.products"))
    if form.errors:
        flash("Controleer de gemarkeerde velden.", "error")
    return render_template("admin/product_form.html", form=form, product=None)


@admin_bp.route("/producten/<int:product_id>/bewerken", methods=["GET", "POST"])
def product_edit(product_id: int):
    product = db.get_or_404(Product, product_id)
    form = ProductForm(obj=product)  # the price property fills the price field
    if form.validate_on_submit():
        _apply_product_form(product, form)
        db.session.commit()
        flash(f"Product '{product.name}' is bijgewerkt.", "success")
        return redirect(url_for("admin.products"))
    if form.errors:
        flash("Controleer de gemarkeerde velden.", "error")
    return render_template("admin/product_form.html", form=form, product=product)


@admin_bp.post("/producten/<int:product_id>/verwijderen")
def product_delete(product_id: int):
    product = db.get_or_404(Product, product_id)
    used_in_orders = db.session.scalar(
        select(func.count(OrderItem.id)).where(OrderItem.product_id == product.id)
    )
    if used_in_orders:
        # Keep the row so existing orders stay complete; hide it from the shop instead.
        product.is_active = False
        product.featured = False
        db.session.commit()
        flash(
            f"'{product.name}' komt voor in bestellingen en is daarom verborgen in plaats van verwijderd.",
            "info",
        )
    else:
        db.session.delete(product)
        db.session.commit()
        flash(f"'{product.name}' is verwijderd.", "success")
    return redirect(url_for("admin.products"))


# ---- Orders (story 9) ----------------------------------------------------------
@admin_bp.route("/bestellingen")
def orders():
    status = request.args.get("status", "")
    if status and status not in ORDER_STATUSES:
        flash("Onbekende status, we tonen alle bestellingen.", "info")
        status = ""

    stmt = select(Order).order_by(Order.created_at.desc(), Order.id.desc())
    if status:
        stmt = stmt.where(Order.status == status)
    counts = dict(db.session.execute(select(Order.status, func.count(Order.id)).group_by(Order.status)).all())
    return render_template(
        "admin/orders.html",
        orders=db.session.scalars(stmt).all(),
        status=status,
        counts=counts,
        total_count=sum(counts.values()),
    )


@admin_bp.route("/bestellingen/<int:order_id>")
def order_detail(order_id: int):
    return render_template("admin/order_detail.html", order=db.get_or_404(Order, order_id))


@admin_bp.post("/bestellingen/<int:order_id>/status")
def order_status(order_id: int):
    order = db.get_or_404(Order, order_id)
    new_status = request.form.get("status", "")
    if new_status not in ORDER_STATUSES:
        flash("Ongeldige status.", "error")
    elif new_status != order.status:
        order.status = new_status
        db.session.commit()
        flash(f"Bestelling {order.number} staat nu op '{new_status}'.", "success")
    return redirect(_safe_next(request.form.get("next")) or url_for("admin.order_detail", order_id=order.id))

