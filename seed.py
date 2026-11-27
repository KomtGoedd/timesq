"""Fill the database with demo data: 12 products, an admin and a test customer.

Usage:  python seed.py

WARNING: drops and recreates all tables, so existing data is lost.
The accounts below are local test accounts only; never reuse these passwords.
"""
from datetime import datetime, timedelta, timezone

from app import create_app
from app import placeholders as art
from app.cart import shipping_cents_for
from app.extensions import db
from app.models import ROLE_ADMIN, ROLE_CUSTOMER, Order, OrderItem, Product, User

# Test accounts (documented in the README).
TEST_USERS = [
    {"name": "Beheerder Time Square", "email": "admin@example.com", "password": "Admin123!", "role": ROLE_ADMIN},
    {"name": "Sanne de Vries", "email": "klant@example.com", "password": "Klant123!", "role": ROLE_CUSTOMER},
]

# name, category, price in cents, stock, featured, description, artwork
PRODUCTS = [
    # --- Klassieke horloges ------------------------------------------------
    (
        "Meridian Automatic", "klassiek", 34900, 8, True,
        "Automatisch uurwerk met 42 uur gangreserve, saffierglas en een kast van 40 mm in "
        "goudkleurig staal. De zwarte wijzerplaat met gouden indexen is ingetogen én opvallend. "
        "Waterdicht tot 10 ATM.",
        art.analog_watch("goud", "#0F0F11", "#141416"),
    ),
    (
        "Noorder Chronograaf", "klassiek", 27900, 5, False,
        "Quartz-chronograaf met stopwatchfunctie tot 60 minuten, een zilverkleurige kast van "
        "42 mm en een diepblauwe wijzerplaat. Geïnspireerd op de luchtvaart, gebouwd voor elke dag.",
        art.analog_watch("zilver", "#13233F", "#2A1B12", 1, 50, chrono=True, label="CHRONOGRAPH"),
    ),
    (
        "Grachten Classic 38", "klassiek", 18900, 12, False,
        "Een tijdloze dress watch: 38 mm, een ultraplat quartz-uurwerk en een zilverwitte "
        "wijzerplaat met slanke indexen. Geleverd met een leren band in cognac.",
        art.analog_watch("zilver", "#ECEBE6", "#8B5A2B", 8, 20, label="QUARTZ"),
    ),
    (
        "Amstel Heritage Gold", "klassiek", 44900, 0, False,
        "Onze limited edition met automatisch uurwerk, open caseback en een champagnekleurige "
        "wijzerplaat in een kast van 39 mm. Genummerd en geleverd in een walnoten box.",
        art.analog_watch("goud", "#D9C7A0", "#3B2414", 3, 40, label="LIMITED EDITION"),
    ),
    # --- Smartwatches & fitnesstrackers -----------------------------------
    (
        "Pulse S2 Smartwatch", "smartwatch", 22900, 15, True,
        "AMOLED-scherm van 1,9 inch, hartslag- en slaapmeting, ingebouwde gps en tot 7 dagen "
        "batterij. Meldingen van je telefoon, contactloos betalen en meer dan 100 sportmodi.",
        art.smart_watch("zwart", "#18181B"),
    ),
    (
        "Pulse Active Tracker", "smartwatch", 8995, 25, True,
        "Lichte fitnesstracker van slechts 24 gram. Meet stappen, hartslag, stress en slaap, met "
        "tot 14 dagen batterijduur. Waterdicht tot 5 ATM, dus ook geschikt om mee te zwemmen.",
        art.smart_watch("zwart", "#2F3B32", slim=True, stat="8.421", progress=0.84),
    ),
    (
        "Pulse Pro Titanium", "smartwatch", 39900, 3, False,
        "Titanium kast, saffierglas en een helder always-on display. Met ecg, "
        "bloedzuurstofmeting, dual-band gps en tot 10 dagen batterij. Voor wie het maximale uit "
        "elke training haalt.",
        art.smart_watch("titanium", "#3F3F46", stat="SpO2 98%", progress=0.92),
    ),
    (
        "Stride Run GPS", "smartwatch", 15900, 7, False,
        "Hardloophorloge met nauwkeurige gps, trainingsschema's en realtime tempo- en "
        "hartslagzones. Tot 20 uur batterij in gps-modus en goed afleesbaar in fel zonlicht.",
        art.smart_watch("zilver", "#7C2D12", stat="5:12 /km", progress=0.45),
    ),
    # --- Accessoires --------------------------------------------------------
    (
        "Leren band Cognac 20 mm", "accessoire", 3995, 30, True,
        "Handgemaakte band van volnerf Italiaans leer met contrasterende stiksels. Dankzij de "
        "snelwisselpinnen wissel je zonder gereedschap. Past op alle 20 mm-horloges van Time Square.",
        art.strap("#8B5A2B", "zilver"),
    ),
    (
        "Sportband Siliconen Zwart", "accessoire", 2495, 40, False,
        "Zachte, ademende band van FKM-siliconen. Zweet- en waterbestendig, ideaal voor training "
        "en dagelijks gebruik. Geschikt voor de Pulse S2 en Pulse Pro.",
        art.strap("#232328", "zwart", stitched=False, holes=7),
    ),
    (
        "Magnetische oplader Pulse", "accessoire", 1995, 50, False,
        "Compacte magnetische oplaadpuck met een USB-C-kabel van 1 meter. Klikt direct vast en "
        "laadt je Pulse binnen 90 minuten volledig op.",
        art.charger("zwart"),
    ),
    (
        "Horlogebox Walnoot (6 vakken)", "accessoire", 6900, 6, False,
        "Opbergbox van massief walnotenhout met zes zachte kussens en een glazen deksel. Houdt je "
        "collectie stofvrij en netjes gepresenteerd.",
        art.watch_box(),
    ),
]


# Demo order history for the test customer: (days ago, status, [(product name, quantity)]).
# These are historical orders, so they do not lower the stock above.
DEMO_ORDERS = [
    (12, "Verzonden", [("Grachten Classic 38", 1), ("Leren band Cognac 20 mm", 1)]),
    (3, "In behandeling", [("Pulse Active Tracker", 1)]),
    (0, "Ontvangen", [("Magnetische oplader Pulse", 1)]),
]


def add_demo_orders(customer: User, products_by_name: dict[str, Product]) -> None:
    now = datetime.now(timezone.utc)
    for days_ago, status, lines in DEMO_ORDERS:
        subtotal = sum(products_by_name[name].price_cents * qty for name, qty in lines)
        shipping = shipping_cents_for(subtotal)
        order = Order(
            user=customer,
            status=status,
            created_at=now - timedelta(days=days_ago, hours=2),
            subtotal_cents=subtotal,
            shipping_cents=shipping,
            total_cents=subtotal + shipping,
            shipping_name=customer.name,
            shipping_street="Voorbeeldstraat 12",
            shipping_postal_code="1234 AB",
            shipping_city="Amsterdam",
        )
        for name, qty in lines:
            product = products_by_name[name]
            order.items.append(
                OrderItem(product=product, product_name=product.name, quantity=qty, unit_price_cents=product.price_cents)
            )
        db.session.add(order)


def main() -> None:
    app = create_app()
    with app.app_context():
        art.write_brand_assets()

        db.drop_all()
        db.create_all()

        products_by_name = {}
        for name, category, price_cents, stock, featured, description, svg in PRODUCTS:
            image_url = art.write_image(f"products/{art.slugify(name)}.svg", svg)
            product = Product(
                name=name,
                category=category,
                price_cents=price_cents,
                stock=stock,
                featured=featured,
                description=description,
                image_url=image_url,
            )
            db.session.add(product)
            products_by_name[name] = product

        users = {}
        for data in TEST_USERS:
            user = User(name=data["name"], email=data["email"], role=data["role"])
            user.set_password(data["password"])
            db.session.add(user)
            users[data["role"]] = user

        add_demo_orders(users[ROLE_CUSTOMER], products_by_name)
        db.session.commit()
        print(
            f"Database gevuld: {len(PRODUCTS)} producten, {len(TEST_USERS)} testaccounts "
            f"en {len(DEMO_ORDERS)} voorbeeldbestellingen."
        )


if __name__ == "__main__":
    main()
