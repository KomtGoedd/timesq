"""Application configuration, read from environment variables / the .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

_DEFAULT_DB = (BASE_DIR / "instance" / "timesquare.db").as_posix()


class Config:
    # No fallback on purpose: the app refuses to start without a real secret.
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", f"sqlite:///{_DEFAULT_DB}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Shop rules (amounts in cents to avoid floating point errors).
    FREE_SHIPPING_THRESHOLD_CENTS = 5000  # free shipping from EUR 50.00
    SHIPPING_COST_CENTS = 495  # otherwise EUR 4.95
