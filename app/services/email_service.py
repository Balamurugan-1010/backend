import os
import ssl
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ENV_PATH = os.path.join(ROOT_DIR, ".env")
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_ENV_PATH = os.path.join(BACKEND_DIR, ".env")

def reload_environment():
    """Dynamically reloads environment variables from the project root .env file."""
    if os.path.exists(ENV_PATH):
        load_dotenv(dotenv_path=ENV_PATH, override=True)
    elif os.path.exists(BACKEND_ENV_PATH):
        load_dotenv(dotenv_path=BACKEND_ENV_PATH, override=True)
    else:
        load_dotenv(override=True)

reload_environment()
logger = logging.getLogger("talentmatch.email")


class EmailConfigMissingException(Exception):
    """Raised when SMTP credentials or server host are not configured in environment."""
    pass


class EmailDeliveryException(Exception):
    """Raised when email transmission fails due to SMTP, auth, network or recipient errors."""
    pass


def mask_email(email: str) -> str:
    """Mask email for privacy and secure logging (e.g. j***e@example.com)."""
    if not email or "@" not in email:
        return "***"
    local_part, domain = email.split("@", 1)
    if len(local_part) <= 2:
        masked_local = local_part[0] + "*"
    else:
        masked_local = local_part[0] + "*" * (len(local_part) - 2) + local_part[-1]
    return f"{masked_local}@{domain}"


def is_smtp_configured() -> bool:
    """Check whether mandatory SMTP configuration parameters are set in environment."""
    reload_environment()
    host = os.getenv("SMTP_HOST", "").strip().strip("'\"")
    user = os.getenv("SMTP_USER", "").strip().strip("'\"")
    password = os.getenv("SMTP_PASSWORD", "").strip().strip("'\"")
    return bool(host and user and password)


def send_otp_email(to_email: str, manager_name: str, otp_code: str) -> None:
    """
    Sends a 6-digit OTP verification email to the manager via SMTP.
    Raises EmailConfigMissingException if configuration is missing.
    Raises EmailDeliveryException if transmission fails.
    Never logs or exposes the OTP code or SMTP credentials.
    """
    reload_environment()
    smtp_host = os.getenv("SMTP_HOST", "").strip().strip("'\"")
    smtp_port_raw = os.getenv("SMTP_PORT", "587").strip().strip("'\"")
    smtp_user = os.getenv("SMTP_USER", "").strip().strip("'\"")
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip().strip("'\"")
    smtp_from_email = os.getenv("SMTP_FROM_EMAIL", "").strip().strip("'\"") or smtp_user
    smtp_from_name = os.getenv("SMTP_FROM_NAME", "TalentMatch Security").strip().strip("'\"")
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").strip().strip("'\"").lower() in ("true", "1", "yes")
    smtp_use_ssl = os.getenv("SMTP_USE_SSL", "false").strip().strip("'\"").lower() in ("true", "1", "yes")

    # Format Google 16-character App Passwords if spaced (e.g. 'xxxx xxxx xxxx xxxx' -> 'xxxxxxxxxxxxxxxx')
    if "gmail" in smtp_host.lower() and len(smtp_password.replace(" ", "")) == 16:
        smtp_password = smtp_password.replace(" ", "")

    if not smtp_host or not smtp_user or not smtp_password:
        logger.warning(
            f"SMTP email sending attempted for {mask_email(to_email)}, but SMTP configuration is incomplete in .env."
        )
        raise EmailConfigMissingException(
            "Email service is not configured. Please set SMTP_HOST, SMTP_PORT, SMTP_USER, and SMTP_PASSWORD in .env."
        )

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        smtp_port = 587

    # Build Multipart Email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"TalentMatch Manager Verification Code: {otp_code}"
    msg["From"] = f"{smtp_from_name} <{smtp_from_email}>"
    msg["To"] = to_email

    # Plain Text Fallback
    text_content = f"""TalentMatch • AI Campus Recruitment Platform
Manager Portal Verification

Hello {manager_name},

Your 6-digit verification code to access the TalentMatch Manager Portal is:

    {otp_code}

This code will expire in 5 minutes (300 seconds).

Security Notice:
- Do not share this code with anyone.
- TalentMatch administrators and recruiters will never ask for your verification code.
- If you did not request this login code, please ignore this email or review your account security.

Best regards,
The TalentMatch Team
"""

    # Rich Responsive HTML
    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TalentMatch Verification Code</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1E293B;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #F8FAFC; padding: 32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 520px; background-color: #FFFFFF; border-radius: 20px; border: 1px solid #E2E8F0; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05); overflow: hidden;">
          <!-- Header Banner -->
          <tr>
            <td style="background: linear-gradient(135deg, #1D4ED8 0%, #2563EB 100%); padding: 32px 28px; text-align: center;">
              <div style="display: inline-block; background-color: rgba(255, 255, 255, 0.18); border-radius: 12px; padding: 8px 16px; margin-bottom: 12px;">
                <span style="color: #FFFFFF; font-size: 13px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase;">TalentMatch Security</span>
              </div>
              <h1 style="color: #FFFFFF; font-size: 22px; font-weight: 800; margin: 0; letter-spacing: -0.5px;">Manager Portal Verification</h1>
              <p style="color: #DBEAFE; font-size: 12px; margin: 6px 0 0 0;">AI-Powered Campus Recruitment & Candidate Ranking</p>
            </td>
          </tr>

          <!-- Body Content -->
          <tr>
            <td style="padding: 32px 28px;">
              <p style="margin: 0 0 16px 0; font-size: 14px; line-height: 22px; color: #334155;">
                Hello <strong>{manager_name}</strong>,
              </p>
              <p style="margin: 0 0 24px 0; font-size: 14px; line-height: 22px; color: #475569;">
                A sign-in request was initiated for your TalentMatch Manager account. Use the one-time verification code below to complete your authentication:
              </p>

              <!-- OTP Display Box -->
              <div style="background: #EFF6FF; border: 2px dashed #93C5FD; border-radius: 16px; padding: 24px 16px; text-align: center; margin: 24px 0;">
                <div style="font-size: 11px; font-weight: 700; color: #1D4ED8; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 6px;">
                  Your Verification Code
                </div>
                <div style="font-size: 38px; font-weight: 900; letter-spacing: 10px; color: #1E40AF; font-family: 'Courier New', Courier, monospace;">
                  {otp_code}
                </div>
                <div style="font-size: 12px; color: #64748B; margin-top: 8px;">
                  ⏱ Valid for <strong>5 minutes</strong> (Expires in 300 seconds)
                </div>
              </div>

              <!-- Security Advisory -->
              <div style="background-color: #F8FAFC; border-left: 4px solid #2563EB; border-radius: 8px; padding: 14px 16px; margin: 24px 0;">
                <p style="margin: 0; font-size: 12px; line-height: 18px; color: #475569;">
                  <strong>Important Security Reminder:</strong> Never share this code with anyone. TalentMatch staff will never ask for your verification code via phone, chat, or email.
                </p>
              </div>

              <p style="margin: 20px 0 0 0; font-size: 12px; line-height: 18px; color: #94A3B8;">
                If you did not attempt to sign in to the TalentMatch Manager Portal, please ignore this email. Your account remains secure.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #F8FAFC; border-top: 1px solid #E2E8F0; padding: 20px 28px; text-align: center;">
              <p style="margin: 0; font-size: 11px; color: #94A3B8; line-height: 16px;">
                TalentMatch AI Recruitment • Confidential Communication<br>
                Automated security notification. Please do not reply to this email.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    msg.attach(MIMEText(text_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        if smtp_use_ssl or smtp_port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=15) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                if smtp_use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                server.login(smtp_user, smtp_password)
                server.send_message(msg)

        logger.info(f"Verification OTP email successfully delivered to: {mask_email(to_email)}")

    except smtplib.SMTPAuthenticationError as exc:
        logger.error(f"SMTP authentication failure sending to {mask_email(to_email)}: {str(exc)}")
        raise EmailDeliveryException(
            "SMTP authentication failed. Please verify SMTP_USER and SMTP_PASSWORD credentials in .env."
        )
    except smtplib.SMTPConnectError as exc:
        logger.error(f"SMTP connection error sending to {mask_email(to_email)}: {str(exc)}")
        raise EmailDeliveryException(
            f"Unable to connect to SMTP server '{smtp_host}:{smtp_port}'. Please check host and port settings."
        )
    except Exception as exc:
        logger.error(f"Email delivery error to {mask_email(to_email)}: {type(exc).__name__} - {str(exc)}")
        raise EmailDeliveryException(
            f"Failed to deliver email: {type(exc).__name__} - {str(exc)}"
        )
