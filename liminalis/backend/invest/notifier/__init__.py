"""Notifier module for sending email notifications."""

from backend.invest.notifier.email_sender import EmailConfig, EmailSender
from backend.invest.notifier.email_templates import (
    format_daily_summary_html,
    format_stock_report_html,
)

__all__ = [
    "EmailConfig",
    "EmailSender",
    "format_stock_report_html",
    "format_daily_summary_html",
]
