from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from modules.auth.service import AuthService
from modules.auth.token_service import TokenService
from authlib.integrations.flask_client import OAuth
import os

auth_bp = Blueprint("auth", __name__, template_folder="../../templates")

# OAuth setup — will be initialized with the app
oauth = OAuth()
google_registered = False


def get_google_client():
    """Get or register the Google OAuth client."""
    global google_registered
    if not google_registered:
        oauth.init_app(current_app)
        oauth.register(
            name='google',
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'},
        )
        google_registered = True
    return oauth.google


# ============================================================
# LOGIN
# ============================================================
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("auth.dashboard"))

    if request.method == "POST":
        login_id = request.form.get("login_id")  # username or email
        password = request.form.get("password")

        status, result = AuthService.authenticate_user(login_id, password)

        if status == True:
            session["user_id"] = result.id
            session["username"] = result.username
            session["email"] = result.email
            session["role"] = result.role
            session["tokens"] = result.tokens
            flash("Login successful!", "success")

            if result.is_admin:
                return redirect(url_for("auth.dashboard"))
            return redirect(url_for("auth.dashboard"))

        elif status == "otp_needed":
            # Bypass OTP for existing unverified accounts
            result.is_verified = True
            from database import db
            db.session.commit()
            
            session["user_id"] = result.id
            session["username"] = result.username
            session["email"] = result.email
            session["role"] = result.role
            session["tokens"] = result.tokens
            flash("Login successful! Auto-verified email.", "success")
            return redirect(url_for("auth.dashboard"))

        else:
            flash(result, "danger")

    return render_template("login.html")


# ============================================================
# REGISTER
# ============================================================
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("auth.dashboard"))

    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("auth.register"))

        success, result = AuthService.register_user(username, email, password)
        if success:
            # Bypass OTP in development: forcefully verify the user and auto-login
            AuthService.verify_otp(email, "bypass") # Make sure the user is set to is_verified=True internally
            
            # Fetch user to log them in
            from database.models.user import User
            user = User.query.filter_by(email=email).first()
            if user:
                user.is_verified = True
                from database import db
                db.session.commit()
                
                session["user_id"] = user.id
                session["username"] = user.username
                session["email"] = user.email
                session["role"] = user.role
                session["tokens"] = user.tokens
            
            flash("Account created! You are now logged in.", "success")
            return redirect(url_for("auth.dashboard"))
        else:
            flash(result, "danger")

    return render_template("register.html")


# ============================================================
# OTP VERIFICATION
# ============================================================
@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    email = session.get("pending_email")
    if not email:
        flash("No pending verification. Please login or register.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        otp_code = request.form.get("otp")

        success, result = AuthService.verify_otp(email, otp_code)
        if success:
            session.pop("pending_email", None)
            flash("Email verified! Please login.", "success")
            return redirect(url_for("auth.login"))
        else:
            flash(result, "danger")

    return render_template("verify_otp.html", email=email)


@auth_bp.route("/resend-otp", methods=["POST"])
def resend_otp():
    email = session.get("pending_email") or request.form.get("email")
    if not email:
        flash("No email provided.", "danger")
        return redirect(url_for("auth.register"))

    success, msg = AuthService.resend_otp(email)
    session["pending_email"] = email  # Ensure it's in session
    flash(msg if success else msg, "success" if success else "danger")
    return redirect(url_for("auth.verify_otp"))


# ============================================================
# GOOGLE OAUTH
# ============================================================
@auth_bp.route("/google")
def google_login():
    try:
        google = get_google_client()
        redirect_uri = url_for('auth.google_callback', _external=True)
        return google.authorize_redirect(redirect_uri)
    except Exception as e:
        flash(f"Google OAuth setup error: {str(e)}", "danger")
        return redirect(url_for("auth.login"))


@auth_bp.route("/google/callback")
def google_callback():
    try:
        google = get_google_client()
        token = google.authorize_access_token()
        user_info = token.get('userinfo')
        if not user_info:
            user_info = google.get('https://www.googleapis.com/oauth2/v3/userinfo').json()

        google_id = user_info.get('sub')
        email = user_info.get('email')
        name = user_info.get('name', email.split('@')[0])

        user = AuthService.google_login(google_id, email, name)

        session["user_id"] = user.id
        session["username"] = user.username
        session["email"] = user.email
        session["role"] = user.role
        session["tokens"] = user.tokens
        flash("Logged in with Google!", "success")

        if user.is_admin:
            return redirect(url_for("auth.dashboard"))
        return redirect(url_for("auth.dashboard"))

    except Exception as e:
        flash(f"Google login failed: {str(e)}", "danger")
        return redirect(url_for("auth.login"))


# ============================================================
# LOGOUT
# ============================================================
@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("auth.login"))


# ============================================================
# DASHBOARD
# ============================================================
@auth_bp.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    from database.models.website import Website
    from database.models.user import User

    user = User.query.get(session["user_id"])
    websites = Website.query.filter_by(user_id=session["user_id"]).all()
    token_info = TokenService.get_info(session["user_id"])

    # Update session tokens
    session["tokens"] = user.tokens if user else 0

    return render_template("dashboard.html",
                           username=session.get("username"),
                           websites=websites,
                           user=user,
                           token_info=token_info)


# ============================================================
# PRICING PAGE
# ============================================================
@auth_bp.route("/pricing")
def pricing():
    return render_template("pricing.html")