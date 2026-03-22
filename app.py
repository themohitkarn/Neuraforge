import os
import logging
from flask import Flask, redirect, url_for, render_template, Blueprint, request, jsonify
from database import db
from modules.chatbot.routes import chatbot_bp

try:
    import docker  # type: ignore
except ModuleNotFoundError:
    docker = None

logger = logging.getLogger(__name__)

# ============================================================
# DOCKER CLIENT
# ============================================================
client = None
if docker is None:
    logger.warning("Docker SDK is not installed. Code execution feature is disabled.")
else:
    try:
        client = docker.from_env()
    except Exception as e:
        logger.warning("Docker is not running or unavailable. Code execution is disabled. Error: %s", e)

# ============================================================
# CODE EXECUTION BLUEPRINT
# ============================================================
execution_bp = Blueprint("execution", __name__)


@execution_bp.route("/execute", methods=["POST"])
def handle_execution():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    code = data.get("code")
    filename = data.get("filename", "main.py")

    # HTML execution → handled by preview
    if filename.endswith(".html"):
        return jsonify({
            "type": "frontend",
            "message": "HTML rendered in preview window"
        })

    # Python execution
    if filename.endswith(".py"):
        output = run_persistent_env(user_id, code)
        return jsonify({
            "type": "backend",
            "output": output
        })

    return jsonify({"error": "Unsupported file type"})


# ============================================================
# PERSISTENT PYTHON ENVIRONMENT (Docker)
# ============================================================
def run_persistent_env(user_id, code):

    workspace_id = str(user_id or "anonymous")
    base_path = os.path.abspath(f"user_workspaces/{workspace_id}")
    lib_path = os.path.abspath(f"user_workspaces/{workspace_id}/libs")

    os.makedirs(base_path, exist_ok=True)
    os.makedirs(lib_path, exist_ok=True)

    file_path = os.path.join(base_path, "main.py")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(code)

    if client is None:
        return "Error: Docker environment not available for code execution."

    try:
        container = client.containers.run(
            image="python:3.11-slim",
            command="python /app/main.py",
            volumes={
                base_path: {"bind": "/app", "mode": "rw"},
                lib_path: {"bind": "/usr/local/lib/python3.11/site-packages", "mode": "rw"},
            },
            working_dir="/app",
            mem_limit="128m",
            network_disabled=False,
            remove=True,
            stdout=True,
            stderr=True,
        )

        return container.decode("utf-8")

    except Exception as e:
        return f"Error: {str(e)}"


# ============================================================
# CREATE APP
# ============================================================
def create_app():

    app = Flask(__name__)

    # --------------------------------------------------------
    # BASIC CONFIG
    # --------------------------------------------------------
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///neuraforge.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY", "super-secret-neuraforge-key-123"
    )
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB

    # --------------------------------------------------------
    # INIT DATABASE
    # --------------------------------------------------------
    db.init_app(app)

    # --------------------------------------------------------
    # IMPORT BLUEPRINTS
    # --------------------------------------------------------
    from modules.auth.routes import auth_bp
    from modules.ai_generator.routes import ai_generator_bp
    from modules.website.routes import website_bp

    from modules.website.upload_routes import upload_bp
    from modules.website.feature_routes import features_bp
    from modules.ai_agent.routes import ai_agent_bp

    # --------------------------------------------------------
    # REGISTER BLUEPRINTS
    # --------------------------------------------------------
    app.register_blueprint(chatbot_bp, url_prefix="/api/chat")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(ai_generator_bp, url_prefix="/api/generate")
    app.register_blueprint(website_bp, url_prefix="/website")

    app.register_blueprint(upload_bp, url_prefix="/website")
    app.register_blueprint(features_bp, url_prefix="/website")
    app.register_blueprint(ai_agent_bp)

    # CODE EXECUTION
    app.register_blueprint(execution_bp, url_prefix="/api/code")

    # --------------------------------------------------------
    # ROUTES
    # --------------------------------------------------------
    @app.route("/")
    def home():
        if os.path.exists(os.path.join(app.root_path, "templates", "landing.html")):
            return render_template("landing.html")
        return redirect(url_for("auth.login"))

    @app.route("/dashboard")
    def global_dashboard():
        return redirect(url_for("auth.dashboard"))

    # --------------------------------------------------------
    # CREATE DATABASE TABLES
    # --------------------------------------------------------
    with app.app_context():

        from database.models.user import User
        from database.models.website import Website
        from database.models.page import Page
        from database.models.section import Section
        from database.models.project_file import ProjectFile
        from database.models.ai_feedback import AIFeedback
        from database.models.snapshot import SectionSnapshot
        from database.models.shared_access import SharedAccess

        db.create_all()

    return app


# ============================================================
# RUN APP
# ============================================================
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
