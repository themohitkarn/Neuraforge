from database import db
from database.models.user import User
from core.email_service import EmailService
from datetime import datetime


class AuthService:
    @staticmethod
    def register_user(username, email, password):
        """Register a new user with email OTP verification."""
        existing = User.query.filter_by(email=email).first()

        # If user exists but NOT verified, delete and allow re-registration
        if existing and not existing.is_verified:
            db.session.delete(existing)
            db.session.commit()
            existing = None

        if User.query.filter_by(username=username).first():
            return False, "Username already exists"
        if existing:
            return False, "Email already registered"

        new_user = User(username=username, email=email)
        new_user.set_password(password)

        # Auto-admin for the owner
        if email == "mohitkarn123@gmail.com":
            new_user.role = "admin"
            new_user.tokens = 999999
            new_user.is_verified = True  # Admin auto-verified

        # Generate and send OTP
        otp = EmailService.generate_otp()
        new_user.otp_code = otp
        new_user.otp_expires = EmailService.get_otp_expiry()

        db.session.add(new_user)
        db.session.commit()

        # Send OTP email
        EmailService.send_otp(email, otp)

        return True, new_user

    @staticmethod
    def authenticate_user(login_id, password):
        """Login with username or email. If unverified, redirect to OTP."""
        user = User.query.filter(
            (User.username == login_id) | (User.email == login_id)
        ).first()

        if user and user.check_password(password):
            if not user.is_verified:
                # Resend OTP automatically and return special status
                otp = EmailService.generate_otp()
                user.otp_code = otp
                user.otp_expires = EmailService.get_otp_expiry()
                db.session.commit()
                EmailService.send_otp(user.email, otp)
                return "otp_needed", user  # Special status for redirect
            return True, user
        return False, "Invalid credentials"

    @staticmethod
    def verify_otp(email, otp_code):
        """Verify email OTP."""
        user = User.query.filter_by(email=email).first()
        if not user:
            return False, "User not found"

        if user.is_verified:
            return True, user

        if not user.otp_code or not user.otp_expires:
            return False, "No OTP found. Request a new one."

        if datetime.utcnow() > user.otp_expires:
            return False, "OTP expired. Request a new one."

        if user.otp_code != otp_code:
            return False, "Invalid OTP"

        user.is_verified = True
        user.otp_code = None
        user.otp_expires = None
        db.session.commit()

        return True, user

    @staticmethod
    def resend_otp(email):
        """Resend a new OTP."""
        user = User.query.filter_by(email=email).first()
        if not user:
            return False, "Email not found"

        if user.is_verified:
            return False, "Already verified"

        otp = EmailService.generate_otp()
        user.otp_code = otp
        user.otp_expires = EmailService.get_otp_expiry()
        db.session.commit()

        EmailService.send_otp(email, otp)
        return True, "OTP resent"

    @staticmethod
    def google_login(google_id, email, name):
        """Handle Google OAuth login/register."""
        user = User.query.filter(
            (User.google_id == google_id) | (User.email == email)
        ).first()

        if user:
            if not user.google_id:
                user.google_id = google_id
            user.is_verified = True
            db.session.commit()
            return user

        # Create new user from Google
        new_user = User(
            username=name.replace(" ", "_").lower()[:50],
            email=email,
            google_id=google_id,
            is_verified=True
        )

        if email == "mohitkarn123@gmail.com":
            new_user.role = "admin"
            new_user.tokens = 999999

        db.session.add(new_user)
        db.session.commit()
        return new_user