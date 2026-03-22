from database import db
from datetime import datetime

class Website(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    framework = db.Column(db.String(30), default="tailwind")

    # User feedback
    review = db.Column(db.String(500), nullable=True)
    rating = db.Column(db.Float, nullable=True)

    # Generation metadata
    engine_used = db.Column(db.String(20), nullable=True)  # groq, gemini, local
    layout_used = db.Column(db.String(100), nullable=True)
    output_hash = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    pages = db.relationship("Page", backref="website", lazy=True, cascade="all, delete-orphan")

