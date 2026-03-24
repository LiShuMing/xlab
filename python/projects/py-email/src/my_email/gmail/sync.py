"""
Gmail synchronization module for email inbox MVP.

Provides initial and incremental sync strategies for pulling messages
from Gmail API into the local SQLite database.
"""

from __future__ import annotations

import base64
import re
import socket
from datetime import datetime, timezone
from typing import Any

import httplib2
import structlog
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

from my_email.config import settings
from my_email.db.repository import (
    MessageData,
    get_setting,
    save_setting,
    upsert_message,
)
from my_email.gmail.auth import get_credentials
from my_email.parser.cleaner import clean_email_body

log = structlog.get_logger()


# ── blocked senders (auto-generated notifications) ─────────────────────────────

BLOCKED_SENDERS = {
    # GitHub notifications
    "notifications@github.com",
    "noreply@github.com",
    # Google
    "no-reply@accounts.google.com",
    "no-reply@google.com",
    "noreply@google.com",
    # Common noreply addresses
    "noreply@*",
    "no-reply@*",
    "donotreply@*",
    "do-not-reply@*",
    # Newsletter/bulk senders
    "bounce@*",
    "bounces@*",
}


def _is_blocked_sender(sender_email: str | None) -> bool:
    """
    Check if sender should be filtered out (auto-generated notifications).

    Args:
        sender_email: Email address to check.

    Returns:
        True if sender should be blocked.
    """
    if not sender_email:
        return False

    sender_lower = sender_email.lower()

    for blocked in BLOCKED_SENDERS:
        if blocked.startswith("*@"):
            # Wildcard domain match
            domain = blocked[1:]  # @domain.com
            if sender_lower.endswith(domain):
                return True
        elif blocked.endswith("@*"):
            # Wildcard local part match
            local = blocked[:-1]  # noreply@
            if sender_lower.startswith(local):
                return True
        elif sender_lower == blocked:
            return True

    return False


# ── custom exceptions ─────────────────────────────────────────────────────────


class GmailSyncError(RuntimeError):
    """Base exception for Gmail sync failures."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


class GmailTimeoutError(GmailSyncError):
    """Raised when Gmail API connection times out."""

    def __init__(self, timeout: int, original_error: Exception) -> None:
        super().__init__(
            f"Connection to Gmail API timed out after {timeout}s. "
            "If you are in a region that requires a proxy to access Google services, "
            f"please set GMAIL_PROXY in your .env file (e.g., GMAIL_PROXY=http://127.0.0.1:7890). "
            f"Original error: {original_error}",
            original_error,
        )
        self.timeout = timeout


class GmailConnectionError(GmailSyncError):
    """Raised when Gmail API connection fails."""

    def __init__(self, original_error: Exception) -> None:
        super().__init__(
            f"Failed to connect to Gmail API: {original_error}. "
            "Please check your network connection and proxy settings.",
            original_error,
        )


class HistoryIdExpiredError(GmailSyncError):
    """Raised when Gmail history ID has expired (older than 7 days)."""

    def __init__(self) -> None:
        super().__init__(
            "Gmail history ID has expired. Gmail retains history for approximately 7 days. "
            "A full sync will be performed instead."
        )


# ── Gmail API helpers ─────────────────────────────────────────────────────────


def _build_http() -> httplib2.Http:
    """Build HTTP client with timeout and proxy support."""
    kwargs: dict[str, Any] = {"timeout": settings.gmail_timeout}
    if settings.gmail_proxy:
        proxy_url = settings.gmail_proxy
        if "://" in proxy_url:
            proxy_url = proxy_url.split("://")[-1]
        proxy_host, proxy_port = proxy_url.rsplit(":", 1)
        kwargs["proxy_info"] = httplib2.ProxyInfo(
            proxy_type=httplib2.socks.PROXY_TYPE_HTTP,
            proxy_host=proxy_host,
            proxy_port=int(proxy_port),
        )
    return httplib2.Http(**kwargs)


def build_service() -> Resource:
    """Build authenticated Gmail API service."""
    creds = get_credentials(settings.gmail_credentials_file, settings.gmail_token_file)
    http = _build_http()
    authed_http = AuthorizedHttp(creds, http=http)
    return build("gmail", "v1", http=authed_http)


def _decode_payload(payload: dict[str, Any]) -> tuple[str, str]:
    """
    Recursively extract (raw_text, mime_type) from a Gmail message payload.

    Prefers text/plain over text/html when both are available.
    """
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    if body_data and mime_type in ("text/plain", "text/html"):
        text = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
        return text, mime_type

    parts = payload.get("parts", [])
    for preferred_mime in ("text/plain", "text/html"):
        for part in parts:
            if part.get("mimeType") == preferred_mime:
                result, mt = _decode_payload(part)
                if result:
                    return result, mt
    for part in parts:
        result, mt = _decode_payload(part)
        if result:
            return result, mt

    return "", ""


def extract_email_address(sender: str | None) -> str | None:
    """
    Extract email address from sender string.

    Args:
        sender: Sender string like 'Name <email@example.com>' or 'email@example.com'.

    Returns:
        Email address or None if not found.
    """
    if not sender:
        return None
    match = re.search(r"<([^>]+)>", sender)
    if match:
        return match.group(1)
    if "@" in sender:
        return sender.strip()
    return None


def _determine_msg_state(label_ids: list[str]) -> str:
    """
    Determine message state from Gmail labels.

    Args:
        label_ids: List of Gmail label IDs.

    Returns:
        'unread', 'read', or 'starred'.
    """
    if "STARRED" in label_ids:
        return "starred"
    if "UNREAD" in label_ids:
        return "unread"
    return "read"


def _parse_message(raw: dict[str, Any]) -> MessageData:
    """Parse a raw Gmail message into a structured MessageData dict."""
    headers = {h["name"].lower(): h["value"] for h in raw["payload"].get("headers", [])}

    ts_ms = int(raw.get("internalDate", 0))
    received_at = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    raw_body, mime_hint = _decode_payload(raw["payload"])
    body_text = clean_email_body(raw_body, mime_hint=mime_hint)

    sender = headers.get("from", "")
    sender_email = extract_email_address(sender)

    label_ids = raw.get("labelIds", [])
    msg_state = _determine_msg_state(label_ids)

    return MessageData(
        id=raw["id"],
        thread_id=raw["threadId"],
        subject=headers.get("subject", "(no subject)"),
        sender=sender,
        sender_email=sender_email,
        received_at=received_at,
        body_text=body_text,
    )


# ── sync strategies ───────────────────────────────────────────────────────────


def _fetch_message_refs(service: Resource, query: str) -> list[dict[str, str]]:
    """Page through messages().list and return all message refs matching query."""
    refs: list[dict[str, str]] = []
    page_token = None
    while True:
        params: dict[str, Any] = {
            "userId": "me",
            "q": query,
            "maxResults": settings.gmail_max_results,
        }
        if page_token:
            params["pageToken"] = page_token
        result = service.users().messages().list(**params).execute()
        refs.extend(result.get("messages", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return refs


def _fetch_history_refs(
    service: Resource, start_history_id: str
) -> tuple[list[dict[str, str]], str]:
    """Fetch message refs added since the given history ID."""
    refs: list[dict[str, str]] = []
    new_history_id = start_history_id
    page_token = None
    while True:
        params: dict[str, Any] = {
            "userId": "me",
            "startHistoryId": start_history_id,
            "historyTypes": ["messageAdded"],
        }
        if page_token:
            params["pageToken"] = page_token
        result = service.users().history().list(**params).execute()
        new_history_id = result.get("historyId", new_history_id)
        for item in result.get("history", []):
            for added in item.get("messagesAdded", []):
                refs.append(added["message"])
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return refs, new_history_id


def _ingest_refs(
    service: Resource, refs: list[dict[str, str]], db_conn: Any
) -> dict[str, int]:
    """Fetch full messages for each ref and upsert into DB."""
    synced = 0
    skipped = 0
    errors = 0

    for ref in refs:
        try:
            raw = service.users().messages().get(
                userId="me", id=ref["id"], format="full"
            ).execute()

            msg = _parse_message(raw)

            # Filter out blocked senders (auto-generated notifications)
            if _is_blocked_sender(msg.get("sender_email")):
                skipped += 1
                log.debug("gmail.sync.blocked", id=msg["id"], sender=msg.get("sender_email"))
                continue

            if upsert_message(db_conn, msg):
                synced += 1
                log.info("gmail.sync.inserted", id=msg["id"], subject=msg["subject"][:80])
        except HttpError as e:
            errors += 1
            log.warning("gmail.sync.fetch_error", id=ref["id"], error=str(e))

    if skipped > 0:
        log.info("gmail.sync.filtered", skipped=skipped)

    return {"synced": synced, "skipped": skipped, "errors": errors}


# ── public entry points ───────────────────────────────────────────────────────


def sync_messages(
    db_conn: Any, service: Resource | None = None, days: int = 7
) -> dict[str, Any]:
    """
    Sync recent messages from Gmail.

    Uses incremental sync if history_id is available, falls back to full sync.

    Args:
        db_conn: Database connection.
        service: Optional pre-built Gmail service (for testing).
        days: Number of days to sync for full sync.

    Returns:
        Dict with 'synced', 'skipped', 'errors', and 'history_id' keys.
    """
    if service is None:
        service = build_service()

    last_history_id = get_setting(db_conn, "last_history_id")

    try:
        profile = service.users().getProfile(userId="me").execute()
        current_history_id = profile["historyId"]
    except (TimeoutError, socket.timeout) as e:
        log.error("gmail.sync.timeout", error=str(e))
        raise GmailTimeoutError(settings.gmail_timeout, e) from e
    except socket.error as e:
        log.error("gmail.sync.socket_error", error=str(e))
        raise GmailConnectionError(e) from e

    # Try incremental sync if we have a history_id
    if last_history_id:
        try:
            refs, new_history_id = _fetch_history_refs(service, last_history_id)
            log.info("gmail.sync.incremental", count=len(refs))
            result = _ingest_refs(service, refs, db_conn)
            save_setting(db_conn, "last_history_id", new_history_id)
            db_conn.commit()
            result["history_id"] = new_history_id
            return result
        except HttpError as e:
            if e.resp.status == 404:
                log.warning("gmail.sync.history_expired", error=str(e))
                # Fall through to full sync
            else:
                raise

    # Full sync
    query = f"after:{(datetime.now(timezone.utc).replace(hour=0, minute=0, second=0) - __import__('datetime').timedelta(days=days)).strftime('%Y/%m/%d')}"
    if settings.gmail_filter_query:
        query = f"{settings.gmail_filter_query} {query}"

    refs = _fetch_message_refs(service, query)
    log.info("gmail.sync.full", count=len(refs))
    result = _ingest_refs(service, refs, db_conn)
    save_setting(db_conn, "last_history_id", current_history_id)
    db_conn.commit()
    result["history_id"] = current_history_id
    return result