"""WeChat H5 OAuth routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from backend.db.engine import get_session_factory
from backend.services import wechat_service
from backend.settings import Settings, get_settings
from backend.wechat.client import WeChatOAuthError, build_official_oauth_url

router = APIRouter(prefix="/api/wechat", tags=["wechat"])


@router.get("/official/oauth/start")
def start_official_oauth(
    target: str = Query(default=wechat_service.DEFAULT_TARGET),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    return _redirect_to_official_oauth(target, settings)


@router.get("/official/entry/{tab}")
def start_official_tab_entry(
    tab: str,
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    target = wechat_service.target_for_tab(tab)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown WeChat H5 tab: {tab}",
        )
    return _redirect_to_official_oauth(target, settings)


def _redirect_to_official_oauth(target: str, settings: Settings) -> RedirectResponse:
    app_id = settings.wechat_official_app_id
    redirect_uri = settings.wechat_official_oauth_redirect_uri
    if not app_id or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WeChat Official Account OAuth is not configured",
        )

    state = wechat_service.create_oauth_state(settings, target=target)
    return RedirectResponse(
        build_official_oauth_url(
            app_id=app_id,
            redirect_uri=redirect_uri,
            scope=settings.wechat_official_oauth_scope,
            state=state,
        )
    )


@router.get("/official/oauth/callback")
async def official_oauth_callback(
    code: str,
    state: str,
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    try:
        if settings.postgres_configured and not settings.wechat_official_mock_openid:
            factory = get_session_factory()
            async with factory() as session:
                result = await wechat_service.complete_official_oauth(
                    code=code,
                    state=state,
                    settings=settings,
                    session=session,
                )
        else:
            result = await wechat_service.complete_official_oauth(
                code=code,
                state=state,
                settings=settings,
                session=None,
            )
    except wechat_service.WeChatStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except WeChatOAuthError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return RedirectResponse(wechat_service.build_frontend_callback_url(result))
