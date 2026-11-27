"""Time Square web shop - Flask application factory."""
import os

from flask import Flask, flash, redirect, render_template, request, send_from_directory, url_for
from flask_wtf.csrf import CSRFError

from .config import Config
from .extensions import csrf, db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY is not set. Copy .env.example to .env and fill in a random secret."
        )

    os.makedirs(app.instance_path, exist_ok=True)

    # Extensions
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Log in om verder te gaan."
    login_manager.login_message_category = "info"

    # Import models so SQLAlchemy knows every table (and the user loader is registered).
    from . import models  # noqa: F401
    from .routes import register_blueprints
    from .utils import register_template_helpers

    register_blueprints(app)
    register_template_helpers(app)
    _register_error_handlers(app)

    @app.route("/sw.js")
    def service_worker():
        """Serve the service worker from the site root so it may control every page."""
        response = send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")
        response.headers["Cache-Control"] = "no-cache"
        return response

    return app


def _register_error_handlers(app):
    @app.errorhandler(CSRFError)
    def csrf_error(_error):
        # Usually an expired session or a form left open too long: just try again.
        flash("Je sessie is verlopen. Probeer het nog een keer.", "error")
        target = request.referrer if request.referrer and request.referrer.startswith(request.host_url) else None
        return redirect(target or url_for("shop.home"))

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_error):
        db.session.rollback()  # leave the session usable after a failed transaction
        return render_template("errors/500.html"), 500
