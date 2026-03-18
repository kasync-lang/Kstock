from datetime import timedelta, datetime

import jwt
from app.core.config import KeyStore
from jwt.exceptions import InvalidTokenError
from datetime import datetime, timedelta, timezone
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from email.message import Message, EmailMessage
import jwt
from jinja2 import Template
from jwt.exceptions import InvalidTokenError
from app.core.config import settings
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
logger = logging.getLogger(__name__)
@dataclass
class EmailData:
    html_content: str
    subject: str


def render_email_template(*, template_name:str, context:dict[str, Any]) -> str:
    template_str = (
        Path(__file__).parent / "email-template" / "build" / template_name
    ).read_text()
    html_content = Template(template_str).render(context)
    return html_content

def send_email(
    *,
    email_to: str,
    subject: str = "",
    html_content: str = "",
) -> None:
    assert settings.emails_enabled, "No provided configuration for email variables"

    # Tạo email message (MIME)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
    msg["To"] = email_to

    # Nội dung HTML
    part = MIMEText(html_content, "html")
    msg.attach(part)

    try:
        if settings.SMTP_SSL:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)

        # Bắt tay TLS nếu có
        if settings.SMTP_TLS and not settings.SMTP_SSL:
            server.starttls()

        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

        server.sendmail(
            settings.EMAILS_FROM_EMAIL,
            [email_to],
            msg.as_string(),
        )
        logger.info("Email sent successfully to %s", email_to)
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        raise
    finally:
        server.quit()

def generate_test_email(email_to: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} test"
    html_content = render_email_template(
        template_name="test_email.html",
        context={"project_name": project_name, "email_to": email_to},
    )
    return EmailData(html_content=html_content, subject=subject)
def generate_reset_password_email(email_to:str, email:str, token:str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Password recovery for user {email}"
    link = f"{settings.FRONTEND_HOST}/reset-password?token={token}"
    html_content = render_email_template(
        template_name="reset_password.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "username": email,
            "email": email_to,
            "valid_hours": settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
            "link": link,
        },
    )
    return EmailData(html_content=html_content, subject=subject)

def generate_signup_verify_email( email:str, token:str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Signup verification for user {email}"
    verify_link = f"{settings.FRONTEND_HOST}/signup-verify?token={token}"
    html_content = render_email_template(
        template_name="verify_email.html",
        context={
            "app_name": settings.PROJECT_NAME,
            "username": email,
            "expiry_hours": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            "verify_link": verify_link,
            "year": datetime.now().year,
        }
    )
    return EmailData(html_content=html_content, subject=subject)
def generate_new_account_email(
    email_to: str, username: str, password: str
) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - New account for user {username}"
    print(username, password, email_to)
    html_content = render_email_template(
        template_name="new_account.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "username": username,
            "password": password,
            "email": email_to,
            "link": settings.FRONTEND_HOST,
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def verify_password_reset_token(token:str) -> str| None:
    try:
        decoded_token = jwt.decode(token, key= KeyStore.public_key, algorithms=[settings.ALGORITHM])
        return str(decoded_token["sub"])
    except InvalidTokenError:
        return None
def generate_password_reset_token(email:str) -> str:
    delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    now = datetime.now(timezone.utc)
    expires = now + delta
    exp = expires.timestamp()
    encoded_jwt = jwt.encode(
        {"exp":exp,"nbf":now,"sub":email},
        KeyStore.private_key,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


