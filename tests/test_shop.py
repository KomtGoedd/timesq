"""End-to-end tests for the user stories. Run with:  python -m unittest -v

Each test gets a fresh in-memory database, so the real database is never touched.
"""
import re
import unittest

from sqlalchemy import func, select

from app import create_app
from app import cart as shop_cart
from app.config import Config
from app.extensions import db
from app.models import ROLE_ADMIN, ROLE_CUSTOMER, Order, Product, User

PASSWORD = "Wachtwoord1!"


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False


class ShopTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()

        self.watch = Product(name="Testhorloge", category="klassiek", price_cents=30000, stock=2,
                             featured=True, description="Automatisch", image_url="img/hero.svg")
        self.strap = Product(name="Testband", category="accessoire", price_cents=2000, stock=10,
                             description="Leer", image_url="img/hero.svg")
        self.sold_out = Product(name="Uitverkocht model", category="smartwatch", price_cents=10000, stock=0,
                                description="Op", image_url="img/hero.svg")
        self.hidden = Product(name="Verborgen model", category="klassiek", price_cents=5000, stock=5,
                              description="Weg", image_url="img/hero.svg", is_active=False)
        self.admin = User(name="Admin Test", email="admin@example.com", role=ROLE_ADMIN)
        self.customer = User(name="Klant Test", email="klant@example.com", role=ROLE_CUSTOMER)
        for user in (self.admin, self.customer):
            user.set_password(PASSWORD)
        db.session.add_all([self.watch, self.strap, self.sold_out, self.hidden, self.admin, self.customer])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.ctx.pop()

    # ---- helpers -------------------------------------------------------------
    def login(self, email="klant@example.com", password=PASSWORD):
        return self.client.post("/inloggen", data={"email": email, "password": password})

    def add(self, product, quantity=1):
        return self.client.post(f"/winkelmand/toevoegen/{product.id}", data={"aantal": quantity})

    def cart(self):
        with self.client.session_transaction() as session:
            return dict(session.get("cart", {}))

    def checkout(self, **overrides):
        data = {"name": "Klant Test", "street": "Voorbeeldstraat 12", "postal_code": "1234ab", "city": "Amsterdam"}
        data.update(overrides)
        return self.client.post("/afrekenen", data=data)

    def order_count(self):
        return db.session.scalar(select(func.count(Order.id)))

    # ---- story 1: homepage ------------------------------------------------------
    def test_home_shows_featured_products_and_categories(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn("Testhorloge", html)
        for slug in ("klassiek", "smartwatch", "accessoire"):
            self.assertIn(f"/producten?categorie={slug}", html)

    def test_unknown_page_shows_friendly_404(self):
        response = self.client.get("/bestaat-niet")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Pagina niet gevonden", response.get_data(as_text=True))

    # ---- story 2: overview ------------------------------------------------------
    def test_filter_sort_and_search(self):
        html = self.client.get("/producten?categorie=accessoire").get_data(as_text=True)
        self.assertIn("Testband", html)
        self.assertNotIn("Testhorloge", html)

        html = self.client.get("/producten?sort=prijs-laag").get_data(as_text=True)
        self.assertLess(html.index("Testband"), html.index("Testhorloge"))
        html = self.client.get("/producten?sort=prijs-hoog").get_data(as_text=True)
        self.assertLess(html.index("Testhorloge"), html.index("Testband"))

        html = self.client.get("/producten?q=BAND").get_data(as_text=True)
        self.assertIn("Testband", html)
        self.assertNotIn("Testhorloge", html)

        self.assertNotIn("Verborgen model", self.client.get("/producten").get_data(as_text=True))

    # ---- story 3: detail ----------------------------------------------------------
    def test_sold_out_product_has_disabled_button(self):
        html = self.client.get(f"/product/{self.sold_out.id}").get_data(as_text=True)
        self.assertIn("Niet op voorraad", html)
        submit = re.search(r'<button type="submit"[^>]*>', html).group(0)
        self.assertIn("disabled", submit)
        self.assertEqual(self.client.get(f"/product/{self.hidden.id}").status_code, 404)

    # ---- story 4: cart --------------------------------------------------------------
    def test_cart_quantity_never_exceeds_stock(self):
        self.add(self.watch, 5)
        self.assertEqual(self.cart(), {str(self.watch.id): 2})
        self.add(self.sold_out)
        self.assertNotIn(str(self.sold_out.id), self.cart())

        self.client.post(f"/winkelmand/bijwerken/{self.watch.id}", data={"aantal": 9})
        self.assertEqual(self.cart()[str(self.watch.id)], 2)
        self.client.post(f"/winkelmand/bijwerken/{self.watch.id}", data={"aantal": 0})
        self.assertEqual(self.cart(), {})

    def test_shipping_costs(self):
        self.assertEqual(shop_cart.shipping_cents_for(4999), 495)
        self.assertEqual(shop_cart.shipping_cents_for(5000), 0)

        self.add(self.strap, 1)  # 20,00 -> + 4,95
        html = self.client.get("/winkelmand").get_data(as_text=True)
        self.assertIn("€\xa04,95", html)
        self.assertIn("€\xa024,95", html)

        self.add(self.strap, 2)  # 60,00 -> free
        html = self.client.get("/winkelmand").get_data(as_text=True)
        self.assertIn("Gratis", html)
        self.assertIn("€\xa060,00", html)

    # ---- story 5: accounts ------------------------------------------------------------
    def test_register_login_logout(self):
        response = self.client.post("/registreren", data={
            "name": "Nieuwe Klant", "email": "Nieuw@Example.com", "password": PASSWORD, "password_confirm": PASSWORD,
        })
        self.assertEqual(response.status_code, 302)
        user = db.session.scalar(select(User).where(User.email == "nieuw@example.com"))
        self.assertIsNotNone(user)
        self.assertNotEqual(user.password_hash, PASSWORD)  # stored hashed
        self.client.post("/uitloggen")

        duplicate = self.client.post("/registreren", data={
            "name": "Dubbel", "email": "klant@example.com", "password": PASSWORD, "password_confirm": PASSWORD,
        })
        self.assertIn("Er bestaat al een account", duplicate.get_data(as_text=True))

        wrong = self.login(password="fout-wachtwoord")
        self.assertIn("horen niet bij elkaar", wrong.get_data(as_text=True))
        self.assertEqual(self.login().status_code, 302)
        self.assertEqual(self.client.get("/account/").status_code, 200)

    # ---- story 6: checkout ---------------------------------------------------------------
    def test_checkout_requires_login(self):
        response = self.client.get("/afrekenen")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/inloggen", response.headers["Location"])

    def test_checkout_validates_address(self):
        self.login()
        self.add(self.strap)
        response = self.checkout(postal_code="12345", street="Geen nummer")
        html = response.get_data(as_text=True)
        self.assertIn("Nederlandse postcode", html)
        self.assertIn("huisnummer", html)
        self.assertEqual(self.order_count(), 0)

    def test_checkout_places_order_and_lowers_stock(self):
        self.login()
        self.add(self.watch, 2)
        self.add(self.strap, 1)
        response = self.checkout()
        self.assertEqual(response.status_code, 302)
        self.assertIn("/bevestiging", response.headers["Location"])

        order = db.session.scalar(select(Order))
        self.assertEqual(order.total_cents, 2 * 30000 + 2000)  # free shipping
        self.assertEqual(order.shipping_postal_code, "1234 AB")
        self.assertEqual(db.session.get(Product, self.watch.id).stock, 0)
        self.assertEqual(db.session.get(Product, self.strap.id).stock, 9)
        self.assertEqual(self.cart(), {})

        html = self.client.get(response.headers["Location"]).get_data(as_text=True)
        self.assertIn("Betaling geslaagd", html)
        self.assertIn(order.number, html)

    def test_checkout_stops_when_stock_ran_out(self):
        self.login()
        self.add(self.watch, 2)
        self.watch.stock = 1  # someone else bought one in the meantime
        db.session.commit()
        response = self.checkout()
        self.assertIn("/winkelmand", response.headers["Location"])
        self.assertEqual(self.order_count(), 0)

    def test_place_order_is_atomic(self):
        with self.app.test_request_context():
            shop_cart.set_quantity(self.strap.id, 1)
            shop_cart.set_quantity(self.watch.id, 2)
            summary = shop_cart.load_cart()
        db.session.execute(Product.__table__.update().where(Product.id == self.watch.id).values(stock=1))
        db.session.commit()
        with self.assertRaises(shop_cart.OutOfStockError):
            shop_cart.place_order(self.customer, summary, name="A", street="B 1", postal_code="1234 AB", city="C")
        self.assertEqual(db.session.get(Product, self.strap.id).stock, 10)  # rolled back
        self.assertEqual(self.order_count(), 0)

    # ---- story 7: my orders ------------------------------------------------------------------
    def test_customer_sees_own_orders_only(self):
        self.login()
        self.add(self.strap)
        self.checkout()
        order = db.session.scalar(select(Order))
        html = self.client.get("/account/bestellingen").get_data(as_text=True)
        self.assertIn(order.number, html)
        self.assertIn("Ontvangen", html)
        self.client.post("/uitloggen")

        self.login("admin@example.com")  # any other account
        self.assertEqual(self.client.get(f"/account/bestellingen/{order.id}").status_code, 404)

    # ---- stories 8-9: admin --------------------------------------------------------------------
    def test_admin_pages_require_admin_role(self):
        self.assertEqual(self.client.get("/beheer/producten").status_code, 302)  # to login
        self.login()
        self.assertEqual(self.client.get("/beheer/producten").status_code, 403)
        self.assertEqual(self.client.get("/beheer/bestellingen").status_code, 403)
        self.client.post("/uitloggen")
        self.login("admin@example.com")
        self.assertEqual(self.client.get("/beheer/producten").status_code, 200)
        self.assertEqual(self.client.get("/beheer/bestellingen").status_code, 200)

    def test_admin_product_crud(self):
        self.login("admin@example.com")
        data = {"name": "Nieuw horloge", "description": "Mooi", "price": "1.249,95", "stock": "3",
                "category": "klassiek", "image_url": "", "is_active": "y"}
        self.assertEqual(self.client.post("/beheer/producten/nieuw", data=data).status_code, 302)
        product = db.session.scalar(select(Product).where(Product.name == "Nieuw horloge"))
        self.assertEqual(product.price_cents, 124995)
        self.assertEqual(product.image_url, "img/categories/klassiek.svg")

        invalid = self.client.post("/beheer/producten/nieuw", data=dict(data, price="abc", stock="-1"))
        self.assertIn("geldige prijs", invalid.get_data(as_text=True))

        self.client.post(f"/beheer/producten/{product.id}/bewerken", data=dict(data, price="99", stock="7"))
        db.session.refresh(product)
        self.assertEqual((product.price_cents, product.stock), (9900, 7))

        # The edit form shows the price in Dutch notation in a text input (not type=number).
        edit_html = self.client.get(f"/beheer/producten/{product.id}/bewerken").get_data(as_text=True)
        self.assertRegex(edit_html, r'<input[^>]*name="price"[^>]*type="text"[^>]*value="99,00"')

        self.client.post(f"/beheer/producten/{product.id}/verwijderen")
        self.assertIsNone(db.session.get(Product, product.id))

    def test_deleting_ordered_product_hides_it(self):
        self.login()
        self.add(self.strap)
        self.checkout()
        self.client.post("/uitloggen")
        self.login("admin@example.com")
        self.client.post(f"/beheer/producten/{self.strap.id}/verwijderen")
        product = db.session.get(Product, self.strap.id)
        self.assertIsNotNone(product)
        self.assertFalse(product.is_active)

    def test_admin_updates_order_status(self):
        self.login()
        self.add(self.strap)
        self.checkout()
        order = db.session.scalar(select(Order))
        self.client.post("/uitloggen")

        self.login("admin@example.com")
        self.client.post(f"/beheer/bestellingen/{order.id}/status", data={"status": "Verzonden"})
        db.session.refresh(order)
        self.assertEqual(order.status, "Verzonden")
        self.client.post(f"/beheer/bestellingen/{order.id}/status", data={"status": "Kwijt"})
        db.session.refresh(order)
        self.assertEqual(order.status, "Verzonden")


if __name__ == "__main__":
    unittest.main()
