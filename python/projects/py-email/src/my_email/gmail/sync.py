import base64
import json
import socket
from datetime import datetime, timezone

import httplib2
import structlog
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from my_email.config import settings
from my_email.db.repository import get_sync_state, save_sync_state, upsert_message
from my_email.gmail.auth import get_credentials
from my_email.parser.cleaner import clean_email_body

log = structlog.get_logger()


# ── Gmail API helpers ─────────────────────────────────────────────────────────

def _build_http():
    """Build HTTP client with timeout and proxy support."""
    kwargs = {"timeout": settings.gmail_timeout}
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


def build_service():
    creds = get_credentials(settings.gmail_credentials_file, settings.gmail_token_file)
    http = _build_http()
    authed_http = AuthorizedHttp(creds, http=http)
    return build("gmail", "v1", http=authed_http)


def _decode_payload(payload: dict) -> tuple[str, str]:
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


def _parse_message(raw: dict) -> dict:
    headers = {h["name"].lower(): h["value"] for h in raw["payload"].get("headers", [])}

    ts_ms = int(raw.get("internalDate", 0))
    received_at = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    raw_body, mime_hint = _decode_payload(raw["payload"])
    body_text = clean_email_body(raw_body, mime_hint=mime_hint)

    return {
        "id": raw["id"],
        "thread_id": raw["threadId"],
        "subject": headers.get("subject", "(no subject)"),
        "sender": headers.get("from", ""),
        "received_at": received_at,
        "labels": json.dumps(raw.get("labelIds", [])),
        "body_text": body_text,
    }


# ── sync strategies ───────────────────────────────────────────────────────────

def _fetch_message_refs(service, query: str) -> list[dict]:
    """Page through messages().list and return all message refs matching query."""
    refs = []
    page_token = None
    while True:
        params = {"userId": "me", "q": query, "maxResults": settings.gmail_max_results}
        if page_token:
            params["pageToken"] = page_token
        result = service.users().messages().list(**params).execute()
        refs.extend(result.get("messages", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return refs


def _fetch_history_refs(service, start_history_id: str) -> tuple[list[dict], str]:
    """
    Return (message_refs_added, new_history_id) via users.history.list.
    Note: history API does not support query filtering — we filter post-hoc in _ingest.
    """
    refs = []
    new_history_id = start_history_id
    page_token = None
    while True:
        params = {
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


def _message_matches_filter(raw: dict, query: str) -> bool:
    """Check if a message matches the Gmail query filter.
    
    Supports: is:unread, is:read, label:, from:, to:, subject:, etc.
    """
    if not query or query.strip() == "is:unread":
        # Default: check unread label
        labels = raw.get("labelIds", [])
        return "UNREAD" in labels
    
    query = query.strip().lower()
    labels = [l.lower() for l in raw.get("labelIds", [])]
    headers = {h["name"].lower(): h["value"].lower() for h in raw["payload"].get("headers", [])}
    
    # Parse simple query patterns
    # is:unread, is:read
    if query == "is:unread":
        return "unread" in labels
    if query == "is:read":
        return "unread" not in labels
    
    # label:xxx
    if query.startswith("label:"):
        label_name = query[6:].strip().lower()
        return label_name in labels
    
    # from:xxx
    if query.startswith("from:"):
        from_addr = headers.get("from", "")
        search = query[5:].strip()
        return search in from_addr
    
    # to:xxx  
    if query.startswith("to:"):
        to_addr = headers.get("to", "")
        search = query[3:].strip()
        return search in to_addr
    
    # subject:xxx
    if query.startswith("subject:"):
        subject = headers.get("subject", "")
        search = query[8:].strip()
        return search in subject
    
    # Default: accept all (complex queries not supported in incremental sync)
    return True


def _ingest_refs(service, refs: list[dict], db_conn) -> int:
    """Fetch full messages for each ref and upsert into DB. Returns count inserted."""
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
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── public entry points ───────────────────────────────────────────────────────

def initial_sync(db_conn) -> tuple[int, str]:
    """
    Full sync: fetch all messages matching the filter query.
    Stores the current historyId so subsequent runs can use incremental_sync.
    Returns (inserted_count, history_id).
    """
    service = build_service()

    try:
        profile = service.users().getProfile(userId="me").execute()
    except (TimeoutError, socket.timeout) as e:
        log.error("gmail.sync.timeout", error=str(e))
        raise RuntimeError(
            f"Connection to Gmail API timed out after {settings.gmail_timeout}s. "
            "If you are in a region that requires a proxy to access Google services, "
            f"please set GMAIL_PROXY in your .env file (e.g., GMAIL_PROXY=http://127.0.0.1:7890). "
            f"Original error: {e}"
        ) from e
    except socket.error as e:
        log.error("gmail.sync.socket_error", error=str(e))
        raise RuntimeError(
            f"Failed to connect to Gmail API: {e}. "
            "Please check your network connection and proxy settings."
        ) from e
    
    history_id = profile["historyId"]

    refs = _fetch_message_refs(service, settings.gmail_filter_query)
    log.info("gmail.initial_sync.found", count=len(refs))

    total = _ingest_refs(service, refs, db_conn)
    save_sync_state(db_conn, history_id, _now_utc())
    db_conn.commit()
    log.info("gmail.initial_sync.done", inserted=total, history_id=history_id)
    return total, history_id


def incremental_sync(db_conn) -> tuple[int, str]:
    """
    Incremental sync using stored historyId.
    Falls back to initial_sync if history has expired (Gmail retains ~7 days).
    Returns (inserted_count, new_history_id).
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
        raise RuntimeError(
            f"Connection to Gmail API timed out after {settings.gmail_timeout}s. "
            "If you are in a region that requires a proxy to access Google services, "
            f"please set GMAIL_PROXY in your .env file (e.g., GMAIL_PROXY=http://127.0.0.1:7890). "
            f"Original error: {e}"
        ) from e
    except socket.error as e:
        log.error("gmail.sync.socket_error", error=str(e))
        raise RuntimeError(
            f"Failed to connect to Gmail API: {e}. "
            "Please check your network connection and proxy settings."
        ) from e

    log.info("gmail.incremental_sync.found", count=len(refs))
    total = _ingest_refs(service, refs, db_conn)
    save_sync_state(db_conn, new_history_id, _now_utc())
    db_conn.commit()
    log.info("gmail.incremental_sync.done", inserted=total, new_history_id=new_history_id)
    return total, new_history_id
