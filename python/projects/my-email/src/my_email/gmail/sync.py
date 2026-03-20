import base64
import json
from datetime import datetime, timezone

import structlog
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from my_email.config import settings
from my_email.db.repository import get_sync_state, save_sync_state, upsert_message
from my_email.gmail.auth import get_credentials
from my_email.parser.cleaner import clean_email_body

log = structlog.get_logger()


# ── Gmail API helpers ─────────────────────────────────────────────────────────

def build_service():
    creds = get_credentials(settings.gmail_credentials_file, settings.gmail_token_file)
    return build("gmail", "v1", credentials=creds)


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


def _ingest_refs(service, refs: list[dict], db_conn) -> int:
    """Fetch full messages for each ref and upsert into DB. Returns count inserted."""
    total = 0
    for ref in refs:
        try:
            raw = service.users().messages().get(
                userId="me", id=ref["id"], format="full"
            ).execute()
            msg = _parse_message(raw)
            if upsert_message(db_conn, msg):
                total += 1
                log.info("gmail.sync.inserted", id=msg["id"], subject=msg["subject"][:80])
        except HttpError as e:
            log.warning("gmail.sync.fetch_error", id=ref["id"], error=str(e))
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

    profile = service.users().getProfile(userId="me").execute()
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

    log.info("gmail.incremental_sync.found", count=len(refs))
    total = _ingest_refs(service, refs, db_conn)
    save_sync_state(db_conn, new_history_id, _now_utc())
    db_conn.commit()
    log.info("gmail.incremental_sync.done", inserted=total, new_history_id=new_history_id)
    return total, new_history_id
