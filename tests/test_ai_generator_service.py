import json
import uuid
from pathlib import Path

import pytest
from flask import Flask

import modules.ai_generator.service as ai_service
from database import db
from database.models.page import Page
from database.models.project_file import ProjectFile
from database.models.section import Section
from database.models.user import User
from database.models.website import Website
from modules.ai_generator.design_memory import design_memory
from modules.ai_generator.service import AIGeneratorService


@pytest.fixture
def app_ctx():
    app = Flask(__name__)
    tmp_dir = Path("tmp")
    tmp_dir.mkdir(exist_ok=True)
    db_file = (tmp_dir / f"ai_generator_test_{uuid.uuid4().hex}.db").resolve()
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_file.as_posix()}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "test-secret"
    db.init_app(app)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _create_user(tokens=50):
    user = User(username="tester", email="tester@example.com", role="user", tokens=tokens, is_verified=True)
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


def _sample_site_data(name="Graph Site"):
    return {
        "website_name": name,
        "framework": "tailwind",
        "pages": [
            {
                "name": "Home",
                "slug": "home",
                "sections": [
                    {
                        "name": "Hero",
                        "content": "<section><h1>Graph-powered website</h1><p>Validated pipeline output.</p></section>",
                        "order": 0,
                    }
                ],
            }
        ],
        "files": [{"path": "styles/site.css", "content": "body{margin:0;}"}],
    }


def test_generate_website_uses_langgraph_for_groq_and_deducts_tokens(app_ctx, monkeypatch):
    user = _create_user(tokens=50)
    design_memory.clear(user.id)

    class FakeGraph:
        called = False

        def generate(self, **_kwargs):
            self.called = True
            return _sample_site_data("Groq Graph Site"), None, {"retry_count": 0}

    fake_graph = FakeGraph()
    monkeypatch.setattr(ai_service, "_get_langgraph_pipeline", lambda: fake_graph)
    monkeypatch.setattr(ai_service, "_graph_pipeline_error", None)
    monkeypatch.setattr(ai_service, "_get_router", lambda: pytest.fail("Router should not be used for groq engine"))

    website, error = AIGeneratorService.generate_website(
        prompt="Build a premium startup website",
        user_id=user.id,
        framework="tailwind",
        engine="groq",
    )

    db.session.refresh(user)
    assert error is None
    assert website is not None
    assert website.name == "Groq Graph Site"
    assert website.engine_used == "groq"
    assert fake_graph.called is True
    assert user.tokens == 40
    assert Website.query.count() == 1
    assert Page.query.count() == 1
    assert Section.query.count() == 1
    assert ProjectFile.query.count() == 1


def test_generate_website_uses_legacy_router_for_gemini(app_ctx, monkeypatch):
    user = _create_user(tokens=50)
    design_memory.clear(user.id)

    class FakeRouter:
        called = False

        def generate(self, **_kwargs):
            self.called = True
            return json.dumps(_sample_site_data("Gemini Legacy Site"))

    fake_router = FakeRouter()
    monkeypatch.setattr(ai_service, "_get_router", lambda: fake_router)
    monkeypatch.setattr(ai_service, "_get_langgraph_pipeline", lambda: pytest.fail("LangGraph should not be used for gemini engine"))

    website, error = AIGeneratorService.generate_website(
        prompt="Build a clean business website",
        user_id=user.id,
        framework="tailwind",
        engine="gemini",
    )

    db.session.refresh(user)
    assert error is None
    assert website is not None
    assert website.name == "Gemini Legacy Site"
    assert fake_router.called is True
    assert user.tokens == 40


def test_failed_groq_generation_does_not_deduct_tokens(app_ctx, monkeypatch):
    user = _create_user(tokens=50)
    design_memory.clear(user.id)

    class FailingGraph:
        def generate(self, **_kwargs):
            return None, "mock graph failure", {"retry_count": 2}

    monkeypatch.setattr(ai_service, "_get_langgraph_pipeline", lambda: FailingGraph())
    monkeypatch.setattr(ai_service, "_graph_pipeline_error", None)

    website, error = AIGeneratorService.generate_website(
        prompt="Build me a website",
        user_id=user.id,
        framework="tailwind",
        engine="groq",
    )

    db.session.refresh(user)
    assert website is None
    assert "mock graph failure" in error
    assert user.tokens == 50
