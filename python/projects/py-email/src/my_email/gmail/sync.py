"""
Gmail synchronization module.

Provides initial and incremental sync strategies for pulling messages
from Gmail API into the local SQLite database.

Error handling:
- Connection errors raise descriptive RuntimeError with proxy guidance
- History expiration (7-day limit) triggers automatic fallback to full sync
"""

from __future__ import annotations

import base64
import json
import socket
from datetime import datetime, timezone
from typing import Any

import httplib2
import structlog
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

from my_email.config import settings
from my_email.db.repository import get_sync_state, save_sync_state, upsert_message, MessageData
from my_email.gmail.auth import get_credentials
from my_email.parser.cleaner import clean_email_body

log = structlog.get_logger()


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


# ── Gmail API helpers ─────────────────────────────────────────────────────────

def _build_http() -> httplib2.Http:
    """
    Build HTTP client with timeout and proxy support.

    Returns:
        Configured httplib2.Http instance.
    """
    kwargs: dict[str, Any] = {"timeout": settings.gmail_timeout}
    if settings.gmail_proxy:
        proxy_url = settings.gmail_proxy
        # Parse proxy URL: http://host:port
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
    """
    Build authenticated Gmail API service.

    Returns:
        Configured googleapiclient Resource for Gmail v1 API.
    """
    creds = get_credentials(settings.gmail_credentials_file, settings.gmail_token_file)
    http = _build_http()
    authed_http = AuthorizedHttp(creds, http=http)
    return build("gmail", "v1", http=authed_http)


def _decode_payload(payload: dict[str, Any]) -> tuple[str, str]:
    """
    Recursively extract (raw_text, mime_type) from a Gmail message payload.

    Prefers text/plain over text/html when both are available.

    Args:
        payload: Gmail message payload dict.

    Returns:
        Tuple of (text_content, mime_type).
    """
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    if body_data and mime_type in ("text/plain", "text/html"):
        text = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
        return text, mime_type

    parts = payload.get("parts", [])
    # Prefer text/plain first
    for preferred_mime in ("text/plain", "text/html"):
        for part in parts:
            if part.get("mimeType") == preferred_mime:
                result, mt = _decode_payload(part)
                if result:
                    return result, mt
    # Recurse into nested multipart
    for part in parts:
        result, mt = _decode_payload(part)
        if result:
            return result, mt

    return "", ""


def _parse_message(raw: dict[str, Any]) -> MessageData:
    """
    Parse a raw Gmail message into a structured MessageData dict.

    Args:
        raw: Gmail API message response.

    Returns:
        MessageData dict ready for database insertion.
    """
    headers = {h["name"].lower(): h["value"] for h in raw["payload"].get("headers", [])}

    ts_ms = int(raw.get("internalDate", 0))
    received_at = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    raw_body, mime_hint = _decode_payload(raw["payload"])
    body_text = clean_email_body(raw_body, mime_hint=mime_hint)

    return MessageData({
        "id": raw["id"],
        "thread_id": raw["threadId"],
        "subject": headers.get("subject", "(no subject)"),
        "sender": headers.get("from", ""),
        "received_at": received_at,
        "labels": json.dumps(raw.get("labelIds", [])),
        "body_text": body_text,
    })


# ── sync strategies ───────────────────────────────────────────────────────────

def _fetch_message_refs(service: Resource, query: str) -> list[dict[str, str]]:
    """
    Page through messages().list and return all message refs matching query.

    Args:
        service: Gmail API service.
        query: Gmail search query.

    Returns:
        List of message refs with 'id' and 'threadId' keys.
    """
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
    """
    Fetch message refs added since the given history ID.

    Args:
        service: Gmail API service.
        start_history_id: Starting history ID for incremental sync.

    Returns:
        Tuple of (message_refs, new_history_id).

    Note:
        History API does not support query filtering — we filter post-hoc.
    """
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


def _message_matches_filter(raw: dict[str, Any], query: str) -> bool:
    """
    Check if a message matches the Gmail query filter.

    Supports: is:unread, is:read, label:, from:, to:, subject:, after:, before:

    Args:
        raw: Gmail API message response.
        query: Gmail search query string.

    Returns:
        True if message matches all filter conditions.

    Note:
        Used for incremental sync filtering after Gmail API list.
        For initial_sync, Gmail API already filters.
    """
    if not query or query.strip() == "is:unread":
        # Default: check unread label
        labels = raw.get("labelIds", [])
        return "UNREAD" in labels

    query = query.strip().lower()
    labels = [label.lower() for label in raw.get("labelIds", [])]
    headers = {h["name"].lower(): h["value"] for h in raw["payload"].get("headers", [])}
    headers_lower = {key: value.lower() for key, value in headers.items()}

    # Parse query into tokens and check each condition
    tokens = query.split()

    for token in tokens:
        # Label conditions
        if token in ("is:unread", "is:read") or token.startswith("label:"):
            if not _check_label_condition(labels, token):
                return False
            continue

        # Header conditions
        if token.startswith(("from:", "to:", "subject:")):
            if not _check_header_condition(headers_lower, token):
                return False
            continue

        # Date conditions
        if token.startswith(("after:", "before:")):
            if not _check_date_condition(raw, token):
                return False
            continue

    # All conditions passed
    return True


def _check_label_condition(labels: list[str], token: str) -> bool:
    """Check if a label condition is satisfied."""
    if token == "is:unread":
        return "unread" in labels
    if token == "is:read":
        return "unread" not in labels
    if token.startswith("label:"):
        label_name = token[6:].strip().lower()
        return label_name in labels
    return True


def _check_header_condition(
    headers_lower: dict[str, str], token: str
) -> bool:
    """Check if a header condition (from, to, subject) is satisfied."""
    if token.startswith("from:"):
        from_addr = headers_lower.get("from", "")
        search = token[5:].strip().lower().replace("(", "").replace(")", "")
        return search in from_addr
    if token.startswith("to:"):
        to_addr = headers_lower.get("to", "")
        search = token[3:].strip().lower()
        return search in to_addr
    if token.startswith("subject:"):
        subject = headers_lower.get("subject", "")
        search = token[8:].strip().lower()
        return search in subject.lower()
    return True


def _check_date_condition(raw: dict[str, Any], token: str) -> bool:
    """Check if a date condition (after, before) is satisfied."""
    try:
        msg_ts = int(raw.get("internalDate", 0))
        msg_date = datetime.fromtimestamp(msg_ts / 1000, tz=timezone.utc)

        if token.startswith("after:"):
            date_str = token[6:].strip()
            after_date = datetime.strptime(date_str, "%Y/%m/%d").replace(tzinfo=timezone.utc)
            return msg_date >= after_date
        if token.startswith("before:"):
            date_str = token[7:].strip()
            before_date = datetime.strptime(date_str, "%Y/%m/%d").replace(tzinfo=timezone.utc)
            return msg_date <= before_date
    except ValueError:
        pass  # Invalid date format, accept
    return True


def _ingest_refs(service: Resource, refs: list[dict[str, str]], db_conn: Any) -> int:
    """
    Fetch full messages for each ref and upsert into DB.

    Args:
        service: Gmail API service.
        refs: List of message refs.
        db_conn: Database connection.

    Returns:
        Number of messages inserted.
    """
    total = 0
    skipped = 0
    for ref in refs:
        try:
            raw = service.users().messages().get(
                userId="me", id=ref["id"], format="full"
            ).execute()

            # Apply filter for incremental sync
            if not _message_matches_filter(raw, settings.gmail_filter_query):
                skipped += 1
                continue

            msg = _parse_message(raw)
            if upsert_message(db_conn, msg):
                total += 1
                log.info("gmail.sync.inserted", id=msg["id"], subject=msg["subject"][:80])
        except HttpError as e:
            log.warning("gmail.sync.fetch_error", id=ref["id"], error=str(e))

    if skipped > 0:
        log.info("gmail.sync.filtered", skipped=skipped)
    return total


def _now_utc() -> str:
    """Return current UTC timestamp as ISO-8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── public entry points ───────────────────────────────────────────────────────

def initial_sync(db_conn: Any) -> tuple[int, str]:
    """
    Full sync: fetch all messages matching the filter query.

    Stores the current historyId so subsequent runs can use incremental_sync.

    Args:
        db_conn: Database connection.

    Returns:
        Tuple of (inserted_count, history_id).

    Raises:
        GmailTimeoutError: If connection times out.
        GmailConnectionError: If connection fails.
    """
    service = build_service()

    try:
        profile = service.users().getProfile(userId="me").execute()
    except (TimeoutError, socket.timeout) as e:
        log.error("gmail.sync.timeout", error=str(e))
        raise GmailTimeoutError(settings.gmail_timeout, e) from e
    except socket.error as e:
        log.error("gmail.sync.socket_error", error=str(e))
        raise GmailConnectionError(e) from e

    history_id = profile["historyId"]

    refs = _fetch_message_refs(service, settings.gmail_filter_query)
    log.info("gmail.initial_sync.found", count=len(refs))

    total = _ingest_refs(service, refs, db_conn)
    save_sync_state(db_conn, history_id, _now_utc())
    db_conn.commit()
    log.info("gmail.initial_sync.done", inserted=total, history_id=history_id)
    return total, history_id


def incremental_sync(db_conn: Any) -> tuple[int, str]:
    """
    Incremental sync using stored historyId.

    Falls back to initial_sync if history has expired (Gmail retains ~7 days).

    Args:
        db_conn: Database connection.

    Returns:
        Tuple of (inserted_count, new_history_id).

    Raises:
        GmailTimeoutError: If connection times out.
        GmailConnectionError: If connection fails.
    """
    state = get_sync_state(db_conn)
    if not state:
        log.info("gmail.incremental_sync.no_state_fallback")
        return initial_sync(db_conn)

    service = build_service()
    try:
        refs, new_history_id = _fetch_history_refs(service, state["history_id"])
    except HttpError as e:
        if e.resp.status == 404:
            log.warning("gmail.incremental_sync.history_expired_fallback", error=str(e))
            return initial_sync(db_conn)
        raise
    except (TimeoutError, socket.timeout) as e:
        log.error("gmail.sync.timeout", error=str(e))
        raise GmailTimeoutError(settings.gmail_timeout, e) from e
    except socket.error as e:
        log.error("gmail.sync.socket_error", error=str(e))
        raise GmailConnectionError(e) from e

    log.info("gmail.incremental_sync.found", count=len(refs))
    total = _ingest_refs(service, refs, db_conn)
    save_sync_state(db_conn, new_history_id, _now_utc())
    db_conn.commit()
    log.info("gmail.incremental_sync.done", inserted=total, new_history_id=new_history_id)
    return total, new_history_id