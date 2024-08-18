"""Minimal WeChat Official Account OAuth client."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from backend.settings import Settings

WECHAT_AUTHORIZE_URL = "https://open.weixin.qq.com/connect/oauth2/authorize"
WECHAT_ACCESS_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"


class WeChatOAuthError(RuntimeError):
    """Raised when WeChat OAuth cannot be completed."""


def build_official_oauth_url(
    *,
    app_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
) -> str:
    query = urllib.parse.urlencode(
        {
            "appid": app_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope,
            "state": state,
        }
    )
    return f"{WECHAT_AUTHORIZE_URL}?{query}#wechat_redirect"


def exchange_official_oauth_code(settings: Settings, code: str) -> dict[str, Any]:
    if settings.wechat_official_mock_openid:
        return {
            "openid": settings.wechat_official_mock_openid,
            "unionid": None,
            "scope": settings.wechat_official_oauth_scope,
        }

    app_id = settings.wechat_official_app_id
    app_secret = settings.wechat_official_app_secret
    if not app_id or not app_secret:
        raise WeChatOAuthError("WeChat Official Account app id/secret are not configured")

    query = urllib.parse.urlencode(
        {
            "appid": app_id,
            "secret": app_secret,
            "code": code,
            "grant_type": "authorization_code",
        }
    )
    request = urllib.request.Request(f"{WECHAT_ACCESS_TOKEN_URL}?{query}", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except OSError as exc:
        raise WeChatOAuthError("WeChat OAuth token request failed") from exc

    if "errcode" in payload:
        raise WeChatOAuthError(
            f"WeChat OAuth error {payload.get('errcode')}: {payload.get('errmsg', 'unknown error')}"
        )
    if not payload.get("openid"):
        raise WeChatOAuthError("WeChat OAuth response did not include openid")
    return payload

