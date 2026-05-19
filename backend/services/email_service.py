"""Transactional email helpers."""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def send_password_reset_email(to_email: str, reset_link: str) -> None:
    smtp_host = os.environ.get("SMTP_HOST")
    if not smtp_host:
        if os.environ.get("ENVIRONMENT") != "production":
            logger.info("password reset link generated: %s", reset_link)
            return
        logger.error("SMTP_HOST missing; password reset email not sent")
        return

    msg = EmailMessage()
    msg["Subject"] = "Reset your EduFlow password"
    msg["From"] = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER")
    msg["To"] = to_email
    msg.set_content(
        "Use this link to reset your EduFlow password. The link expires in 15 minutes.\n\n"
        f"{reset_link}\n\n"
        "If you did not request this, ignore this email."
    )

    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
        smtp.starttls()
        if smtp_user and smtp_pass:
            smtp.login(smtp_user, smtp_pass)
        smtp.send_message(msg)


def send_welcome_email(to_email: str, username: str, temp_password: str) -> None:
    smtp_host = os.environ.get("SMTP_HOST")
    if not smtp_host:
        logger.warning("SMTP_HOST missing; welcome email not sent to %s", to_email)
        return

    msg = EmailMessage()
    msg["Subject"] = "Welcome to EduFlow — Your school is ready"
    msg["From"] = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER")
    msg["To"] = to_email
    msg.set_content(
        f"Your EduFlow school has been created.\n\n"
        f"Login URL: {os.environ.get('FRONTEND_URL', '')}/login\n"
        f"Username: {username}\n"
        f"Temporary password: {temp_password}\n\n"
        "You will be prompted to change your password on first login."
    )

    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
        smtp.starttls()
        if smtp_user and smtp_pass:
            smtp.login(smtp_user, smtp_pass)
        smtp.send_message(msg)


def send_operator_completion_email(school_name: str) -> None:
    notify_email = os.environ.get("OPERATOR_NOTIFY_EMAIL")
    smtp_host = os.environ.get("SMTP_HOST")
    if not notify_email or not smtp_host:
        return

    msg = EmailMessage()
    msg["Subject"] = f"EduFlow — School '{school_name}' onboarding complete"
    msg["From"] = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER")
    msg["To"] = notify_email
    msg.set_content(f"School '{school_name}' has completed onboarding (all five setup steps done).")

    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
        smtp.starttls()
        if smtp_user and smtp_pass:
            smtp.login(smtp_user, smtp_pass)
        smtp.send_message(msg)
