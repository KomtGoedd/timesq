"""WTForms forms with Dutch validation messages. CSRF protection comes from FlaskForm."""
from decimal import Decimal, InvalidOperation

from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import BooleanField, DecimalField, IntegerField, PasswordField, SelectField, StringField, TextAreaField
from wtforms.fields.choices import SelectChoice
from wtforms.widgets import TextInput
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
    ValidationError,
)

from .extensions import db
from .models import CATEGORIES, User


# --------------------------------------------------------------------------- #
# Input filters
# --------------------------------------------------------------------------- #
def strip(value):
    return value.strip() if isinstance(value, str) else value


def normalize_email(value):
    return value.strip().lower() if isinstance(value, str) else value


def normalize_postcode(value):
    """'1234ab' / '1234 AB ' -> '1234 AB' (other input is left for the validator)."""
    if not isinstance(value, str):
        return value
    compact = value.replace(" ", "").upper()
    if len(compact) == 6:
        return f"{compact[:4]} {compact[4:]}"
    return value.strip()


# --------------------------------------------------------------------------- #
# Fields that accept Dutch number notation
# --------------------------------------------------------------------------- #
class EuroField(DecimalField):
    """Price field that accepts '49,95', '49.95', '€ 1.249,95' etc.

    Rendered as a text input: a type="number" input would reject the Dutch comma.
    """

    widget = TextInput()

    def _value(self):
        if self.raw_data:
            return self.raw_data[0]
        if self.data is not None:
            return f"{self.data:.2f}".replace(".", ",")
        return ""

    def process_formdata(self, valuelist):
        if not valuelist or not valuelist[0].strip():
            self.data = None
            return
        text = valuelist[0].replace("€", "").replace(" ", "").strip()
        if "," in text:  # Dutch notation: dots are thousand separators
            text = text.replace(".", "").replace(",", ".")
        try:
            value = Decimal(text)
        except InvalidOperation:
            value = None
        if value is None or not value.is_finite():
            self.data = None
            raise ValueError("Vul een geldige prijs in, bijvoorbeeld 49,95.")
        self.data = value


class WholeNumberField(IntegerField):
    def process_formdata(self, valuelist):
        if not valuelist or not valuelist[0].strip():
            self.data = None
            return
        try:
            self.data = int(valuelist[0].strip())
        except ValueError:
            self.data = None
            raise ValueError("Vul een heel getal in.")


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #
class RegisterForm(FlaskForm):
    name = StringField(
        "Naam",
        filters=[strip],
        validators=[DataRequired("Vul je naam in."), Length(2, 120, "Je naam moet 2 tot 120 tekens lang zijn.")],
    )
    email = StringField(
        "E-mailadres",
        filters=[normalize_email],
        validators=[
            DataRequired("Vul je e-mailadres in."),
            Email("Vul een geldig e-mailadres in."),
            Length(max=255, message="Dit e-mailadres is te lang."),
        ],
    )
    password = PasswordField(
        "Wachtwoord",
        validators=[
            DataRequired("Kies een wachtwoord."),
            Length(8, 128, "Je wachtwoord moet minimaal 8 tekens lang zijn."),
        ],
    )
    password_confirm = PasswordField(
        "Herhaal wachtwoord",
        validators=[DataRequired("Herhaal je wachtwoord."), EqualTo("password", "De wachtwoorden komen niet overeen.")],
    )

    def validate_email(self, field):
        if db.session.scalar(select(User.id).where(User.email == field.data)):
            raise ValidationError("Er bestaat al een account met dit e-mailadres. Log in of gebruik een ander adres.")


class LoginForm(FlaskForm):
    email = StringField(
        "E-mailadres",
        filters=[normalize_email],
        validators=[DataRequired("Vul je e-mailadres in."), Length(max=255)],
    )
    password = PasswordField("Wachtwoord", validators=[DataRequired("Vul je wachtwoord in."), Length(max=128)])
    remember = BooleanField("Ingelogd blijven")


# --------------------------------------------------------------------------- #
# Checkout
# --------------------------------------------------------------------------- #
class CheckoutForm(FlaskForm):
    name = StringField(
        "Naam",
        filters=[strip],
        validators=[DataRequired("Vul de naam van de ontvanger in."), Length(2, 120, "Vul een naam van 2 tot 120 tekens in.")],
    )
    street = StringField(
        "Straat en huisnummer",
        filters=[strip],
        validators=[
            DataRequired("Vul je straat en huisnummer in."),
            Length(3, 200, "Vul een geldig adres in."),
            Regexp(r".*\d", message="Vergeet je huisnummer niet."),
        ],
    )
    postal_code = StringField(
        "Postcode",
        filters=[normalize_postcode],
        validators=[
            DataRequired("Vul je postcode in."),
            Regexp(r"^[1-9][0-9]{3} [A-Z]{2}$", message="Vul een Nederlandse postcode in, bijvoorbeeld 1234 AB."),
        ],
    )
    city = StringField(
        "Plaats",
        filters=[strip],
        validators=[DataRequired("Vul je woonplaats in."), Length(2, 100, "Vul een geldige plaatsnaam in.")],
    )


# --------------------------------------------------------------------------- #
# Admin
# --------------------------------------------------------------------------- #
class ProductForm(FlaskForm):
    name = StringField(
        "Naam",
        filters=[strip],
        validators=[DataRequired("Vul een productnaam in."), Length(2, 150, "De naam moet 2 tot 150 tekens lang zijn.")],
    )
    description = TextAreaField(
        "Beschrijving",
        filters=[strip],
        validators=[DataRequired("Vul een beschrijving in."), Length(max=5000, message="Maximaal 5000 tekens.")],
    )
    price = EuroField(
        "Prijs (€)",
        validators=[
            InputRequired("Vul een prijs in."),
            NumberRange(Decimal("0.01"), Decimal("100000"), "De prijs moet tussen € 0,01 en € 100.000 liggen."),
        ],
    )
    stock = WholeNumberField(
        "Voorraad",
        validators=[InputRequired("Vul de voorraad in."), NumberRange(0, 100000, "De voorraad moet 0 of meer zijn.")],
    )
    category = SelectField(
        "Categorie",
        choices=[SelectChoice(value=c.slug, label=c.label) for c in CATEGORIES],
        validators=[DataRequired("Kies een categorie.")],
    )
    image_url = StringField(
        "Afbeelding (URL of pad)",
        filters=[strip],
        validators=[Optional(), Length(max=500, message="Maximaal 500 tekens.")],
    )
    featured = BooleanField("Uitgelicht op de homepage")
    is_active = BooleanField("Zichtbaar in de winkel", default=True)

    def validate_image_url(self, field):
        if field.data and not field.data.startswith(("https://", "http://", "/", "img/")):
            raise ValidationError("Gebruik een volledige URL (https://…) of een pad zoals img/products/naam.svg.")
