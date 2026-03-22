# core/email_service.py
# Email OTP service using Gmail SMTP

import os
import random
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class EmailService:
    """Send OTP emails via Gmail SMTP."""

    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587

    @staticmethod
    def generate_otp() -> str:
        return str(random.randint(100000, 999999))

    @staticmethod
    def send_otp(email: str, otp: str) -> bool:
        """Send a 6-digit OTP to the user's email."""
        sender_email = os.getenv("MAIL_USERNAME")
        sender_password = os.getenv("MAIL_PASSWORD")

        if not sender_email or not sender_password:
            logger.warning("MAIL_USERNAME or MAIL_PASSWORD not set. OTP email skipped.")
            # In dev mode, just log the OTP
            logger.info(f"[DEV MODE] OTP for {email}: {otp}")
            return True

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "🔐 NeuraForge — Verify Your Email"
            msg["From"] = f"NeuraForge <{sender_email}>"
            msg["To"] = email

            html = f"""
            <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 500px; margin: 0 auto; 
                        background: linear-gradient(135deg, #0f172a, #1e1b4b); padding: 40px; border-radius: 16px; color: #e2e8f0;">
                <h1 style="font-size: 24px; margin-bottom: 8px; color: #a78bfa;">⚡ NeuraForge</h1>
                <p style="color: #94a3b8; margin-bottom: 24px;">Verify your email to get started</p>
                
                <div style="background: rgba(99,102,241,0.15); border: 1px solid rgba(99,102,241,0.3); 
                            border-radius: 12px; padding: 24px; text-align: center; margin-bottom: 24px;">
                    <p style="color: #94a3b8; font-size: 14px; margin-bottom: 8px;">Your verification code</p>
                    <h2 style="font-size: 36px; letter-spacing: 8px; font-weight: 700; color: #fff; margin: 0;">
                        {otp}
                    </h2>
                </div>
                
                <p style="color: #64748b; font-size: 13px;">
                    This code expires in <strong>5 minutes</strong>. Don't share it with anyone.
                </p>
            </div>
            """

            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP(EmailService.SMTP_SERVER, EmailService.SMTP_PORT) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, email, msg.as_string())

            logger.info(f"OTP email sent to {email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send OTP email: {e}")
            # Fallback: log the OTP for dev
            logger.info(f"[FALLBACK] OTP for {email}: {otp}")
            return True  # Don't block registration in dev

    @staticmethod
    def get_otp_expiry() -> datetime:
        return datetime.utcnow() + timedelta(minutes=5)
