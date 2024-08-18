"""Email sender with SMTP support and retry logic."""

import asyncio
import os
import smtplib
import socket
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from core.logger import get_logger
from storage import (
    delete_pending_email,
    increment_retry_count,
    log_email,
    save_pending_email,
)

logger = get_logger("notifier.email_sender")

# Default Gmail SMTP settings
GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587

# Retry settings
DEFAULT_MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 300  # 5 minutes
RETRY_BACKOFF_MULTIPLIER = 2


@dataclass
class EmailConfig:
    """Configuration for email sending.

    Attributes:
        smtp_host: SMTP server hostname.
        smtp_port: SMTP server port.
        sender: Sender email address.
        password: SMTP authentication password (App Password for Gmail).
        recipient: Default recipient email address.
    """

    smtp_host: str = GMAIL_SMTP_HOST
    smtp_port: int = GMAIL_SMTP_PORT
    sender: str = ""
    password: str = ""
    recipient: str = ""

    @classmethod
    def from_env(cls) -> "EmailConfig":
        """Create EmailConfig from environment variables.

        Reads:
            GMAIL_APP_PASSWORD: Gmail App Password for SMTP authentication.
            EMAIL_SENDER: Sender email address (optional, defaults to recipient).
            EMAIL_RECIPIENT: Recipient email address.

        Returns:
            EmailConfig instance populated from environment.

        Raises:
            ValueError: If required environment variables are missing.
        """
        password = os.environ.get("GMAIL_APP_PASSWORD", "")
        recipient = os.environ.get("EMAIL_RECIPIENT", "")
        sender = os.environ.get("EMAIL_SENDER", recipient)

        if not password:
            raise ValueError("GMAIL_APP_PASSWORD environment variable is required")
        if not recipient:
            raise ValueError("EMAIL_RECIPIENT environment variable is required")

        return cls(
            smtp_host=GMAIL_SMTP_HOST,
            smtp_port=GMAIL_SMTP_PORT,
            sender=sender,
            password=password,
            recipient=recipient,
        )


class EmailSender:
    """Email sender with retry logic and pending queue integration.

    Provides robust email sending with:
    - Gmail SMTP support with App Password authentication
    - Exponential backoff retry mechanism
    - Automatic pending queue for failed emails
    - Support for both HTML and plain text emails
    """

    def __init__(self, config: EmailConfig):
        """Initialize EmailSender with configuration.

        Args:
            config: EmailConfig instance with SMTP settings.
        """
        self.config = config

    def test_connection(self) -> bool:
        """Test SMTP connection without sending an email.

        Returns:
            True if connection and authentication succeed, False otherwise.
        """
        try:
            with smtplib.SMTP(
                self.config.smtp_host,
                self.config.smtp_port,
                timeout=30,
            ) as server:
                server.starttls()
                server.login(self.config.sender, self.config.password)
                logger.info(
                    "SMTP connection test successful",
                    host=self.config.smtp_host,
                    sender=self.config.sender,
                )
                return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(
                "SMTP authentication failed",
                sender=self.config.sender,
                error=str(e),
            )
            return False

        except smtplib.SMTPException as e:
            logger.error(
                "SMTP connection failed",
                host=self.config.smtp_host,
                error=str(e),
            )
            return False

        except (socket.timeout, ConnectionError, OSError) as e:
            logger.error(
                "Network error during SMTP connection test",
                host=self.config.smtp_host,
                error=str(e),
            )
            return False

    async def send(
        self,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        recipient: Optional[str] = None,
        stock_count: int = 0,
    ) -> bool:
        """Send an email with retry logic.

        Args:
            subject: Email subject line.
            body: Plain text email body.
            html_body: Optional HTML version of the email body.
            recipient: Override recipient email address.
            stock_count: Number of stocks in the report (for logging).

        Returns:
            True if email was sent successfully, False otherwise.
        """
        recipient = recipient or self.config.recipient

        try:
            # Run synchronous SMTP operations in thread pool
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self._send_sync,
                subject,
                body,
                html_body,
                recipient,
            )

            if result:
                # Log successful send
                log_email(
                    recipient=recipient,
                    subject=subject,
                    stock_count=stock_count,
                    status="success",
                )
                logger.info(
                    "Email sent successfully",
                    recipient=recipient,
                    subject=subject,
                )
                return True
            else:
                raise RuntimeError("SMTP send returned False")

        except smtplib.SMTPAuthenticationError as e:
            logger.error(
                "SMTP authentication error",
                recipient=recipient,
                subject=subject,
                error=str(e),
            )
            # Save to pending queue for retry
            save_pending_email(
                recipient=recipient,
                subject=subject,
                body=html_body or body,
            )
            log_email(
                recipient=recipient,
                subject=subject,
                stock_count=stock_count,
                status="failed",
                error_message=f"SMTPAuthenticationError: {e}",
            )
            return False

        except smtplib.SMTPException as e:
            logger.error(
                "SMTP error sending email",
                recipient=recipient,
                subject=subject,
                error=str(e),
            )
            # Save to pending queue for retry
            save_pending_email(
                recipient=recipient,
                subject=subject,
                body=html_body or body,
            )
            log_email(
                recipient=recipient,
                subject=subject,
                stock_count=stock_count,
                status="failed",
                error_message=f"SMTPException: {e}",
            )
            return False

        except (socket.timeout, ConnectionError, OSError) as e:
            logger.error(
                "Network error sending email",
                recipient=recipient,
                subject=subject,
                error=str(e),
            )
            # Save to pending queue for retry
            save_pending_email(
                recipient=recipient,
                subject=subject,
                body=html_body or body,
            )
            log_email(
                recipient=recipient,
                subject=subject,
                stock_count=stock_count,
                status="failed",
                error_message=f"NetworkError: {e}",
            )
            return False

        except Exception as e:
            logger.error(
                "Unexpected error sending email",
                recipient=recipient,
                subject=subject,
                error=str(e),
            )
            # Save to pending queue for retry
            save_pending_email(
                recipient=recipient,
                subject=subject,
                body=html_body or body,
            )
            log_email(
                recipient=recipient,
                subject=subject,
                stock_count=stock_count,
                status="failed",
                error_message=f"UnexpectedError: {e}",
            )
            return False

    def _send_sync(
        self,
        subject: str,
        body: str,
        html_body: Optional[str],
        recipient: str,
    ) -> bool:
        """Synchronous email sending implementation.

        Args:
            subject: Email subject line.
            body: Plain text email body.
            html_body: Optional HTML version of the email body.
            recipient: Recipient email address.

        Returns:
            True if sent successfully.

        Raises:
            SMTPException: If email sending fails.
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.sender
        msg["To"] = recipient

        # Attach plain text version
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Attach HTML version if provided
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(
            self.config.smtp_host,
            self.config.smtp_port,
            timeout=60,
        ) as server:
            server.starttls()
            server.login(self.config.sender, self.config.password)
            server.sendmail(self.config.sender, [recipient], msg.as_string())

        return True

    async def send_with_retry(
        self,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        recipient: Optional[str] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        stock_count: int = 0,
    ) -> bool:
        """Send email with exponential backoff retry.

        Args:
            subject: Email subject line.
            body: Plain text email body.
            html_body: Optional HTML version of the email body.
            recipient: Override recipient email address.
            max_retries: Maximum number of retry attempts.
            stock_count: Number of stocks in the report (for logging).

        Returns:
            True if email was sent successfully, False otherwise.
        """
        recipient = recipient or self.config.recipient

        for attempt in range(1, max_retries + 1):
            logger.info(
                "Attempting to send email",
                recipient=recipient,
                subject=subject,
                attempt=attempt,
                max_retries=max_retries,
            )

            success = await self.send(
                subject=subject,
                body=body,
                html_body=html_body,
                recipient=recipient,
                stock_count=stock_count,
            )

            if success:
                return True

            if attempt < max_retries:
                # Calculate backoff delay with exponential multiplier
                delay = RETRY_DELAY_SECONDS * (RETRY_BACKOFF_MULTIPLIER ** (attempt - 1))
                logger.info(
                    "Retrying email send after delay",
                    recipient=recipient,
                    subject=subject,
                    delay_seconds=delay,
                    next_attempt=attempt + 1,
                )
                await asyncio.sleep(delay)

        logger.error(
            "All retry attempts failed",
            recipient=recipient,
            subject=subject,
            attempts=max_retries,
        )
        return False

    async def send_pending_emails(self) -> tuple[int, int]:
        """Send all pending emails from the queue.

        Returns:
            Tuple of (successful_sends, failed_sends).
        """
        from storage import get_pending_emails

        pending = get_pending_emails(max_retries=DEFAULT_MAX_RETRIES)

        successful = 0
        failed = 0

        for email in pending:
            if email.id is None:
                continue

            logger.info(
                "Retrying pending email",
                email_id=email.id,
                recipient=email.recipient,
                subject=email.subject,
                retry_count=email.retry_count,
            )

            # Check if max retries exceeded
            if email.retry_count >= DEFAULT_MAX_RETRIES:
                logger.warning(
                    "Pending email exceeded max retries, removing",
                    email_id=email.id,
                    retry_count=email.retry_count,
                )
                delete_pending_email(email.id)
                failed += 1
                continue

            # Try to send the email
            success = await self.send(
                subject=email.subject,
                body=email.body,
                html_body=email.html_body,
                recipient=email.recipient,
            )

            if success:
                # Remove from pending queue
                delete_pending_email(email.id)
                successful += 1
            else:
                # Increment retry count
                increment_retry_count(email.id)
                failed += 1

        logger.info(
            "Processed pending emails",
            successful=successful,
            failed=failed,
        )

        return successful, failed