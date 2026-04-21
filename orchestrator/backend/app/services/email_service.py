"""
Email delivery helpers for authentication workflows.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

from app.config import settings
from app.core.logger import get_logger

logger = get_logger("sourcegraph.auth.email")


class EmailDeliveryError(RuntimeError):
    """Raised when the OTP email could not be delivered."""


def missing_smtp_fields() -> list[str]:
    missing: list[str] = []
    if not settings.smtp_host:
        missing.append("SMTP_HOST")
    if not settings.smtp_port:
        missing.append("SMTP_PORT")
    if not settings.smtp_user:
        missing.append("SMTP_USER")
    if not settings.smtp_password:
        missing.append("SMTP_PASSWORD")
    return missing


def _render_otp_email_html(name: str, code: str, expiry_minutes: int) -> str:
    return f"""
    <html>
      <body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,sans-serif;color:#111827;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:32px 16px;">
          <tr>
            <td align="center">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#ffffff;border-radius:14px;border:1px solid #e5e7eb;overflow:hidden;">
                <tr>
                  <td style="padding:24px 28px;background:linear-gradient(135deg,#4C63F7,#7C5CF7);color:#ffffff;">
                    <h1 style="margin:0;font-size:22px;line-height:1.2;">Overwatch Authentication</h1>
                    <p style="margin:8px 0 0 0;font-size:13px;opacity:0.92;">Secure one-time access code</p>
                  </td>
                </tr>
                <tr>
                  <td style="padding:28px;">
                    <p style="margin:0 0 14px 0;font-size:15px;">Hi {name},</p>
                    <p style="margin:0 0 20px 0;font-size:14px;line-height:1.6;color:#374151;">
                      Use the verification code below to continue signing in to Overwatch.
                    </p>
                    <div style="margin:0 0 18px 0;padding:14px 16px;border:1px dashed #9ca3af;border-radius:10px;text-align:center;background:#f9fafb;">
                      <span style="font-size:30px;letter-spacing:8px;font-weight:700;color:#111827;">{code}</span>
                    </div>
                    <p style="margin:0 0 8px 0;font-size:13px;color:#4b5563;">
                      This code expires in <strong>{expiry_minutes} minutes</strong>.
                    </p>
                    <p style="margin:0;font-size:12px;color:#6b7280;">
                      If you did not initiate this request, you can ignore this message.
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """


def _send_smtp_email(to_email: str, subject: str, html_content: str) -> None:
    missing = missing_smtp_fields()
    if missing:
        raise EmailDeliveryError(
            "SMTP is not configured. Missing: " + ", ".join(missing)
        )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email or settings.smtp_user
    message["To"] = to_email
    message.set_content("Your email client does not support HTML messages.")
    message.add_alternative(html_content, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        raise EmailDeliveryError(
            "SMTP authentication failed. Check SMTP_USER/SMTP_PASSWORD."
        ) from exc
    except smtplib.SMTPRecipientsRefused as exc:
        raise EmailDeliveryError("Recipient email was rejected by SMTP server.") from exc
    except (smtplib.SMTPException, TimeoutError, OSError) as exc:
        raise EmailDeliveryError("SMTP delivery failed due to a transport error.") from exc


async def send_otp_email(to_email: str, name: str, code: str) -> None:
    """Send OTP email asynchronously by moving SMTP to a worker thread."""
    subject = "Your Overwatch verification code"
    html = _render_otp_email_html(name=name, code=code, expiry_minutes=settings.otp_expire_minutes)
    await asyncio.to_thread(_send_smtp_email, to_email, subject, html)
    logger.info("OTP email sent to %s", to_email)
