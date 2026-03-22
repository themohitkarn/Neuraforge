from database import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)  # Nullable for Google-only users

    # Role & Tokens
    role = db.Column(db.String(20), default="user")  # "user", "premium", "admin"
    tokens = db.Column(db.Integer, default=50)

    # Google OAuth
    google_id = db.Column(db.String(256), unique=True, nullable=True)

    # Email Verification (OTP)
    is_verified = db.Column(db.Boolean, default=False)
    otp_code = db.Column(db.String(6), nullable=True)
    otp_expires = db.Column(db.DateTime, nullable=True)

    # AI Learning Preferences
    preferred_framework = db.Column(db.String(30), default="tailwind")
    preferred_style = db.Column(db.Text, nullable=True)  # JSON of learned style preferences

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    websites = db.relationship("Website", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin" or self.email == "mohitkarn123@gmail.com"

    @property
    def is_premium(self):
        return self.role in ("premium", "admin")

    @property
    def token_display(self):
        if self.is_admin:
            return "∞"
        return str(self.tokens)