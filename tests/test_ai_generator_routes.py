from types import SimpleNamespace

import pytest
from flask import Blueprint, Flask

import modules.ai_generator.routes as generator_routes
from modules.ai_generator.routes import ai_generator_bp


@pytest.fixture
def route_app(monkeypatch):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "route-test"
    app.register_blueprint(ai_generator_bp, url_prefix="/api/generate")

    auth_bp = Blueprint("auth", __name__)
    website_bp = Blueprint("website_bp", __name__)

    @auth_bp.route("/dashboard")
    def dashboard():
        return "dashboard"

    @website_bp.route("/ide/<int:website_id>")
    def ide_website(website_id):
        return f"ide {website_id}"

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(website_bp, url_prefix="/website")
    return app


def test_generate_route_redirects_to_ide_on_success(route_app, monkeypatch):
    def _success_generate(_prompt, _user_id, framework="tailwind", engine="groq"):
        return SimpleNamespace(id=321), None

    monkeypatch.setattr(generator_routes.AIGeneratorService, "generate_website", _success_generate)

    with route_app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 1

        response = client.post(
            "/api/generate/",
            data={"prompt": "Build a startup site", "framework": "tailwind", "engine": "groq"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/website/ide/321")


def test_generate_route_redirects_to_dashboard_on_failure(route_app, monkeypatch):
    def _failing_generate(_prompt, _user_id, framework="tailwind", engine="groq"):
        return None, "Validation failed after retries"

    monkeypatch.setattr(generator_routes.AIGeneratorService, "generate_website", _failing_generate)

    with route_app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 1

        response = client.post(
            "/api/generate/",
            data={"prompt": "Build a startup site", "framework": "tailwind", "engine": "groq"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/dashboard")
