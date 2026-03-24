"""Notifier module for sending email notifications."""

from notifier.email_sender import EmailConfig, EmailSender
from notifier.email_templates import (
    format_stock_report_html,
    format_daily_summary_html,
)

__all__ = [
    "EmailConfig",
    "EmailSender",
    "format_stock_report_html",
    "format_daily_summary_html",
]