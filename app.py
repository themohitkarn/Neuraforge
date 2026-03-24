import os
from flask import Flask, redirect, url_for, render_template
from database import db
from modules.chatbot.routes import chatbot_bp


# CREATE APP
def create_app():
    app = Flask(__name__)

    # CONFIG
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///neuraforge.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY", "dev-secret-key"
    )
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

    # INIT DB
    db.init_app(app)

    # IMPORT BLUEPRINTS
    from modules.auth.routes import auth_bp
    from modules.ai_generator.routes import ai_generator_bp
    from modules.website.routes import website_bp
    from modules.website.upload_routes import upload_bp
    from modules.website.feature_routes import features_bp
    from modules.ai_agent.routes import ai_agent_bp

    # REGISTER BLUEPRINTS
    app.register_blueprint(chatbot_bp, url_prefix="/api/chat")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(ai_generator_bp, url_prefix="/api/generate")
    app.register_blueprint(website_bp, url_prefix="/website")
    app.register_blueprint(upload_bp, url_prefix="/website")
    app.register_blueprint(features_bp, url_prefix="/website")
    app.register_blueprint(ai_agent_bp)

    # ROUTES
    @app.route("/")
    def home():
        template_path = os.path.join(app.root_path, "templates", "landing.html")
        if os.path.exists(template_path):
            return render_template("landing.html")
        return redirect(url_for("auth.login"))

    @app.route("/dashboard")
    def dashboard():
        return redirect(url_for("auth.dashboard"))

    # INIT DB TABLES
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


# ENTRY POINT
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)