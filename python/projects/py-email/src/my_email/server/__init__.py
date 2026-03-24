"""
Web server module for Email Inbox MVP.

Provides a web interface to:
- Browse and manage emails
- View message details with AI summaries
- Configure sync and retention settings
"""

from my_email.server.app import app

__all__ = ["app"]