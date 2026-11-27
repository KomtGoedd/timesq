# Time Square – webshop (MVP)

Online winkel voor Time Square: klassieke horloges, smartwatches & fitnesstrackers en
accessoires. Gebouwd met Flask, SQLite/SQLAlchemy, Jinja2 en Tailwind CSS (CDN).
De interface is mobile-first en gedraagt zich als een app (tabbalk onderin, installeerbaar
op het beginscherm via "Zet op beginscherm").

## Installatie (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Zet in `.env` een eigen `SECRET_KEY`. Een willekeurige sleutel maak je zo:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Vul daarna de database met voorbeelddata (12 producten + testaccounts) en start de app:

```powershell
python seed.py
python run.py
```

Open <http://127.0.0.1:5000>. Op macOS/Linux activeer je de omgeving met
`source .venv/bin/activate` en gebruik je `cp` in plaats van `Copy-Item`.

> `python seed.py` verwijdert de bestaande database en maakt hem opnieuw aan.
> Het script genereert ook alle placeholder-afbeeldingen in `app/static/img/`.

## Testaccounts (alleen lokaal)

| Rol      | E-mail              | Wachtwoord |
|----------|---------------------|------------|
| Beheerder| `admin@example.com` | `Admin123!`|
| Klant    | `klant@example.com` | `Klant123!`|

De testklant heeft na `python seed.py` al drie voorbeeldbestellingen (Ontvangen, In
behandeling en Verzonden). De beheerpagina's staan onder `/beheer` en zijn alleen
bereikbaar voor gebruikers met de rol `admin`.

## Automatische tests

```powershell
python -m unittest -v
```

De tests (in `tests/test_shop.py`) draaien op een tijdelijke in-memory database en
dekken alle user stories: filters, voorraadgrenzen, verzendkosten, registreren/inloggen,
checkout-validatie, voorraadverlaging, toegang tot bestellingen en de beheerrechten.

## Pagina's

| URL | Pagina |
|-----|--------|
| `/` | Homepage |
| `/producten` | Productoverzicht (`?categorie=`, `?prijs=`, `?sort=`, `?q=`) |
| `/product/<id>` | Productdetail |
| `/winkelmand` | Winkelmand |
| `/afrekenen` | Checkout (inloggen vereist) |
| `/registreren`, `/inloggen` | Account aanmaken / inloggen |
| `/account/`, `/account/bestellingen` | Mijn account en bestellingen |
| `/beheer/producten`, `/beheer/bestellingen` | Beheer (alleen admin) |

## Hoe werkt het

- **Winkelmand** staat in de (ondertekende) sessiecookie, dus werkt ook zonder account en
  blijft bewaard na inloggen. Bij elk bezoek wordt de mand gecontroleerd tegen de actuele
  voorraad.
- **Verzendkosten**: gratis vanaf € 50 subtotaal, anders € 4,95 (instelbaar in `app/config.py`).
- **Bestellen**: de voorraad wordt in één databasetransactie verlaagd met een voorwaardelijke
  update (`WHERE voorraad >= aantal`), zodat het laatste exemplaar nooit twee keer verkocht wordt.
  De betaling is gesimuleerd.
- **Product verwijderen**: komt een product voor in bestellingen, dan wordt het verborgen in
  plaats van verwijderd, zodat de bestelgeschiedenis compleet blijft.
- **Beveiliging**: wachtwoorden gehasht (werkzeug), CSRF-bescherming op alle formulieren,
  `SECRET_KEY` uit `.env`, redirects na inloggen alleen naar eigen pagina's.

## Mappenstructuur

```
app/
  __init__.py      app factory, foutpagina's, service worker-route
  config.py        configuratie uit .env
  extensions.py    db, login manager, CSRF
  models.py        User, Product, Order, OrderItem (+ categorieën en statussen)
  routes.py        blueprints per onderdeel van de winkel
  cart.py          winkelmand (sessie), verzendkosten, bestelling plaatsen
  forms.py         formulieren met Nederlandse validatiemeldingen
  utils.py         euro- en datumnotatie, template-helpers
  placeholders.py  genereert SVG-productfoto's en app-iconen
  templates/       Jinja2-templates (base, partials, shop, errors, ...)
  static/          css, afbeeldingen, manifest.json, sw.js
tests/             automatische tests (unittest)
seed.py            voorbeelddata
run.py             startpunt
```

Bedragen worden in de database als hele centen opgeslagen (geen afrondingsfouten) en in
de interface getoond als `€ 1.234,95`.

## Voortgang user stories

- [x] 1. Homepage met hero, uitgelichte producten en categorieën
- [x] 2. Productoverzicht met filter (categorie, prijs), sortering en zoeken
- [x] 3. Productdetailpagina met voorraadstatus
- [x] 4. Winkelmand met subtotaal, verzendkosten en totaal
- [x] 5. Account aanmaken en inloggen
- [x] 6. Bestelling afronden (gesimuleerde betaling, ordernummer, voorraad verlaagd)
- [x] 7. Mijn bestellingen met status
- [x] 8. Productbeheer (admin)
- [x] 9. Bestellingbeheer met statuswijziging (admin)

## Mogelijke vervolgstappen (buiten scope MVP)

- Echte betalingen (bijv. Mollie of Stripe met iDEAL), inclusief betaalstatus per order
- Productfoto's uploaden in het beheer (nu een URL of pad)
- Productie-deployment: Tailwind bouwen in plaats van de CDN, een WSGI-server (bijv. waitress
  of gunicorn) en een database-migratietool (Flask-Migrate)
- E-mailnotificaties (orderbevestiging, verzendbericht)
- Productreviews en beoordelingen
- Kortingscodes en acties
- Meertaligheid (Engels naast Nederlands)
