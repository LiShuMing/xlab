"""
Web server module for browsing email digests.

Provides a web interface to:
- Browse all available digest dates
- View HTML digest for a specific date
- Trigger sync+summarize for dates without digest
"""

from my_email.server.app import create_app

__all__ = ["create_app"]