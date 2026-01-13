"""Message sending with dry/live modes, retries, and proper rate limiting."""
from __future__ import annotations

import smtplib
import time
from email.message import EmailMessage
from typing import List
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Lead, LeadStatus, Message
from .logging_utils import get_logger
from .tracking import log_event

logger = get_logger(__name__)
settings = get_settings()


def _send_email_smtp(subject: str, body: str, to_addr: str) -> None:
    """Send email via SMTP with optional TLS and authentication."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_username or "outreach@example.com"
    msg["To"] = to_addr
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)


def _simulate_linkedin_dm(body: str, to_profile: str) -> None:
    """Simulate LinkedIn DM sending (compliant with assignment requirements)."""
    logger.info("Simulated LinkedIn DM to %s: %s", to_profile, body[:120])


class RateLimiter:
    """Token bucket-style rate limiter for message sending."""
    
    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self.interval = 60.0 / max_per_minute if max_per_minute > 0 else 0
        self.last_send_time = 0.0
    
    def wait_if_needed(self) -> None:
        """Wait if necessary to respect rate limit."""
        if self.interval <= 0:
            return
        
        now = time.time()
        time_since_last = now - self.last_send_time
        
        if time_since_last < self.interval:
            sleep_time = self.interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_send_time = time.time()


def send_messages(
    session: Session,
    dry_run: bool = True,
    rate_limit_per_minute: int = 10,
    max_retries: int = 2,
) -> List[Lead]:
    """
    Send outreach messages to leads in MESSAGED status.
    
    Args:
        session: Database session
        dry_run: If True, only log messages without actually sending
        rate_limit_per_minute: Maximum messages per minute
        max_retries: Number of retry attempts on failure
    
    Returns:
        List of leads that were successfully processed
    """
    leads = (
        session.query(Lead)
        .filter(Lead.status == LeadStatus.MESSAGED)
        .all()
    )
    
    sent: List[Lead] = []
    failed_count = 0
    rate_limiter = RateLimiter(rate_limit_per_minute)

    for lead in leads:
        message = (
            session.query(Message)
            .filter(Message.lead_id == lead.id)
            .order_by(Message.id.desc())
            .first()
        )
        if not message:
            logger.warning("No message found for lead %s, skipping", lead.id)
            continue

        # Apply rate limiting only in live mode (not needed for dry-run)
        if not dry_run:
            rate_limiter.wait_if_needed()

        attempt = 0
        success = False
        last_error: str | None = None
        
        while attempt <= max_retries and not success:
            try:
                if not dry_run:
                    # Live mode: actually send emails
                    _send_email_smtp(
                        subject="Quick idea for your team",
                        body=message.email_a or "",
                        to_addr=lead.email,
                    )
                    _simulate_linkedin_dm(message.dm_a or "", lead.linkedin)
                else:
                    # Dry-run mode: just log
                    logger.info(
                        "Dry-run send to %s (email: %s)",
                        lead.full_name,
                        lead.email
                    )
                    log_event(
                        session,
                        stage="send",
                        level="INFO",
                        message=f"Dry-run send to {lead.email}",
                        lead_id=lead.id
                    )

                success = True
                
            except Exception as exc:
                last_error = str(exc)
                attempt += 1
                if attempt <= max_retries:
                    # Exponential backoff: 1s, 2s, 4s...
                    backoff = 2 ** (attempt - 1)
                    logger.warning(
                        "Send attempt %d failed for %s, retrying in %ds: %s",
                        attempt, lead.email, backoff, last_error
                    )
                    time.sleep(backoff)
                log_event(
                    session,
                    stage="send",
                    level="ERROR",
                    message=f"Attempt {attempt}: {last_error}",
                    lead_id=lead.id
                )

        if success:
            lead.status = LeadStatus.SENT
            lead.last_error = None
            sent.append(lead)
            log_event(
                session,
                stage="send",
                level="INFO",
                message="Send succeeded",
                lead_id=lead.id
            )
        else:
            lead.status = LeadStatus.FAILED
            lead.last_error = last_error
            failed_count += 1
            log_event(
                session,
                stage="send",
                level="ERROR",
                message=last_error or "Send failed after all retries",
                lead_id=lead.id
            )

    session.commit()
    logger.info(
        "Send step completed: %d sent, %d failed out of %d total",
        len(sent), failed_count, len(leads)
    )
    return sent
