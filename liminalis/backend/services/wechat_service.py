"""WeChat OAuth service and user identity mapping."""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from dataclasses import dataclass
from urllib.parse import quote

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend._shared.auth import issue_access_token
from backend.settings import Settings
from backend.wechat.client import exchange_official_oauth_code
from backend.wechat.db_models import User, UserIdentity

OFFICIAL_PROVIDER = "wechat_official"
DEFAULT_TARGET = "/ego/chat"
ALLOWED_TARGET_PREFIXES = ("/",)
TAB_TARGETS = {
    "ego": "/ego/chat",
    "ego-chat": "/ego/chat",
    "chat": "/ego/chat",
    "code": "/codex",
    "code-lab": "/codex",
    "codex": "/codex",
    "lab": "/codex",
    "logos": "/codex",
    "blog": "/blogs",
    "blogs": "/blogs",
    "radar": "/radar",
    "db-radar": "/radar",
    "database-radar": "/radar",
    "invest": "/invest",
    "value-invest": "/invest",
    "ai": "/ai-chat",
    "ai-chat": "/ai-chat",
}


class WeChatStateError(ValueError):
    """Raised when an OAuth state token is invalid or expired."""


@dataclass(frozen=True)
class WeChatLoginResult:
    token: str
    user_id: str
    account_label: str
    target: str


def create_oauth_state(settings: Settings, *, target: str = DEFAULT_TARGET) -> str:
    serializer = _serializer(settings)
    return serializer.dumps({"target": sanitize_target(target)})


def parse_oauth_state(settings: Settings, state: str) -> dict[str, str]:
    serializer = _serializer(settings)
    try:
        payload = serializer.loads(
            state,
            max_age=settings.wechat_oauth_state_max_age_seconds,
        )
    except SignatureExpired as exc:
        raise WeChatStateError("WeChat OAuth state expired") from exc
    except BadSignature as exc:
        raise WeChatStateError("Invalid WeChat OAuth state") from exc

    return {"target": sanitize_target(str(payload.get("target") or DEFAULT_TARGET))}


def sanitize_target(target: str) -> str:
    target = (target or DEFAULT_TARGET).strip()
    if not target.startswith(ALLOWED_TARGET_PREFIXES) or target.startswith("//"):
        return DEFAULT_TARGET
    if target.startswith("/api/") or target.startswith("/wechat/callback"):
        return DEFAULT_TARGET
    return target


def target_for_tab(tab: str) -> str | None:
    return TAB_TARGETS.get(tab.strip().lower())


async def complete_official_oauth(
    *,
    code: str,
    state: str,
    settings: Settings,
    session: AsyncSession | None,
) -> WeChatLoginResult:
    state_payload = parse_oauth_state(settings, state)
    oauth_payload = await asyncio.to_thread(exchange_official_oauth_code, settings, code)
    app_id = settings.wechat_official_app_id or "mock-official-account"
    openid = str(oauth_payload["openid"])
    unionid = oauth_payload.get("unionid")

    user = (
        await get_or_create_identity_user(
            session,
            provider=OFFICIAL_PROVIDER,
            app_id=app_id,
            openid=openid,
            unionid=str(unionid) if unionid else None,
        )
        if session is not None
        else ephemeral_user(provider=OFFICIAL_PROVIDER, app_id=app_id, openid=openid)
    )
    token = issue_access_token(settings, user_id=user.id)
    label = user.display_name or f"wechat-{openid[-6:]}"
    return WeChatLoginResult(
        token=token,
        user_id=user.id,
        account_label=label,
        target=state_payload["target"],
    )


def ephemeral_user(*, provider: str, app_id: str, openid: str) -> User:
    digest = hashlib.sha256(f"{provider}:{app_id}:{openid}".encode()).hexdigest()[:16]
    return User(id=f"user_{digest}", display_name=f"wechat-{openid[-6:]}")


async def get_or_create_identity_user(
    session: AsyncSession,
    *,
    provider: str,
    app_id: str,
    openid: str,
    unionid: str | None = None,
) -> User:
    result = await session.execute(
        select(UserIdentity).where(
            UserIdentity.provider == provider,
            UserIdentity.app_id == app_id,
            UserIdentity.openid == openid,
        )
    )
    identity = result.scalar_one_or_none()
    if identity is not None:
        user_result = await session.execute(select(User).where(User.id == identity.user_id))
        user = user_result.scalar_one()
        if unionid and identity.unionid != unionid:
            identity.unionid = unionid
            await session.commit()
        return user

    user = User(id=f"user_{uuid.uuid4().hex}", display_name=f"wechat-{openid[-6:]}")
    identity = UserIdentity(
        id=f"identity_{uuid.uuid4().hex}",
        user_id=user.id,
        provider=provider,
        app_id=app_id,
        openid=openid,
        unionid=unionid,
    )
    session.add_all([user, identity])
    await session.commit()
    return user


def build_frontend_callback_url(result: WeChatLoginResult) -> str:
    return (
        "/wechat/callback#"
        f"?token={quote(result.token, safe='')}"
        f"&account_id={quote(result.user_id, safe='')}"
        f"&account_label={quote(result.account_label, safe='')}"
        f"&target={quote(result.target, safe='')}"
    )


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt="wechat-oauth-state")
