import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(
    gmail_address: str,
    gmail_app_password: str,
    to_email: str,
    subject: str,
    body: str,
) -> tuple[bool, str]:
    """
    Send an email via Gmail SMTP using an App Password.
    Returns (success: bool, message: str).

    To get an App Password:
    1. Enable 2-Step Verification on your Google Account
    2. Go to Google Account → Security → App Passwords
    3. Generate a password for "Mail"
    """
    if not gmail_address or not gmail_app_password:
        return False, "Gmail credentials not configured. Go to Settings."

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = gmail_address
        msg["To"] = to_email

        part = MIMEText(body, "plain", "utf-8")
        msg.attach(part)

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(gmail_address, gmail_app_password)
            server.sendmail(gmail_address, to_email, msg.as_string())

        return True, "Email sent successfully."
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed. Check your Gmail address and App Password."
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def test_connection(gmail_address: str, gmail_app_password: str) -> tuple[bool, str]:
    """Test SMTP connection without sending an email."""
    if not gmail_address or not gmail_app_password:
        return False, "Gmail credentials not configured."
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(gmail_address, gmail_app_password)
        return True, "Connected successfully."
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed. Check your Gmail address and App Password."
    except Exception as e:
        return False, f"Connection error: {e}"
