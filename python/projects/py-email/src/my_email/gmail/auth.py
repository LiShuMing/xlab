"""
Gmail OAuth2 authentication module.

Handles the OAuth2 flow for Gmail API access:
- First run: Opens browser for consent, stores token
- Subsequent runs: Refreshes token silently
"""

from __future__ import annotations

from pathlib import Path

import structlog
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

log = structlog.get_logger()

# Gmail readonly scope - only need to read emails
SCOPES: list[str] = ["https://www.googleapis.com/auth/gmail.readonly"]


class AuthError(RuntimeError):
    """Raised when authentication fails."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


def get_credentials(credentials_file: Path, token_file: Path) -> Credentials:
    """
    Load or refresh OAuth2 credentials.

    On first run, opens a local browser for the consent flow and writes token.json.
    Subsequent runs refresh silently via the stored refresh token.

    Args:
        credentials_file: Path to OAuth client secret JSON file.
        token_file: Path to store/load OAuth token.

    Returns:
        Valid OAuth2 credentials.

    Raises:
        AuthError: If credentials file is missing or auth flow fails.
    """
    creds: Credentials | None = None

    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log.info("gmail.auth.refreshing_token")
            creds.refresh(Request())
        else:
            if not credentials_file.exists():
                raise AuthError(
                    f"OAuth client secret not found: {credentials_file}\n"
                    "Download it from Google Cloud Console → APIs & Services → Credentials."
                )
            log.info("gmail.auth.starting_oauth_flow")
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
            creds = flow.run_local_server(port=0)

        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json())
        log.info("gmail.auth.token_saved", path=str(token_file))

    return creds