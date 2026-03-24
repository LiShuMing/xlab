"""Role API routes for AI persona management.

This module provides endpoints for:
- Listing available AI roles
- Getting detailed information about specific roles
- Managing user's current role preference
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.role import PREDEFINED_ROLES, Role
from app.dependencies import get_current_user, get_db
from app.models import User
from app.schemas import ErrorResponse, RoleDetailResponse, RoleResponse, UserResponse

router = APIRouter(prefix="/roles", tags=["roles"])


def _role_to_summary_response(role: Role) -> RoleResponse:
    """Convert a Role to a RoleResponse summary."""
    return RoleResponse(
        id=role.id,
        name=role.name,
        icon=role.icon,
        description=role.description,
    )


def _role_to_detail_response(role: Role) -> RoleDetailResponse:
    """Convert a Role to a RoleDetailResponse with full details."""
    return RoleDetailResponse(
        id=role.id,
        name=role.name,
        icon=role.icon,
        description=role.description,
        system_prompt=role.system_prompt,
        personality={
            "background": role.personality.background,
            "traits": role.personality.traits,
            "speaking_style": role.personality.speaking_style,
            "catchphrases": role.personality.catchphrases,
        },
        knowledge={
            "domain_expertise": role.knowledge.domain_expertise,
            "key_concepts": role.knowledge.key_concepts,
            "classic_quotes": role.knowledge.classic_quotes,
            "references": role.knowledge.references,
        },
        examples=[
            {
                "user_input": ex.user_input,
                "assistant_response": ex.assistant_response,
                "context": ex.context,
            }
            for ex in role.examples
        ],
    )


@router.get(
    "",
    response_model=list[RoleResponse],
    summary="List all roles",
    description="Retrieve a list of all available AI roles with basic information",
)
async def list_roles() -> list[RoleResponse]:
    """List all available AI roles.

    Returns a list of all predefined AI personas that can be used
    for chat sessions. Each role includes basic information like
    id, name, icon, and description.

    Returns:
        list[RoleResponse]: List of available roles.
    """
    return [_role_to_summary_response(role) for role in PREDEFINED_ROLES.values()]


@router.get(
    "/{role_id}",
    response_model=RoleDetailResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get role details",
    description="Get detailed information about a specific AI role including personality, knowledge, and examples",
)
async def get_role_detail(role_id: str) -> RoleDetailResponse:
    """Get detailed information about a specific role.

    Retrieves complete role configuration including system prompt,
    personality traits, knowledge domains, and example dialogues.

    Args:
        role_id: The unique identifier for the role (e.g., 'therapist', 'researcher').

    Returns:
        RoleDetailResponse: Complete role configuration.

    Raises:
        HTTPException: If the role_id is not found (404).
    """
    role = PREDEFINED_ROLES.get(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role '{role_id}' not found",
        )
    return _role_to_detail_response(role)


@router.get(
    "/me/current",
    response_model=RoleResponse,
    summary="Get current role",
    description="Get the current user's preferred AI role",
)
async def get_current_role(
    current_user: User = Depends(get_current_user),
) -> RoleResponse:
    """Get the user's current preferred role.

    Returns the role that the user has selected as their default
    for new chat sessions.

    Args:
        current_user: The authenticated user.

    Returns:
        RoleResponse: The user's current role.
    """
    role = PREDEFINED_ROLES.get(current_user.current_role_id)
    if not role:
        # Fallback to therapist if stored role is invalid
        role = PREDEFINED_ROLES["therapist"]
    return _role_to_summary_response(role)


@router.put(
    "/me/current",
    response_model=UserResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Update current role",
    description="Update the user's preferred AI role",
)
async def update_current_role(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Update the user's current preferred role.

    Changes the default role that will be used for new chat sessions.
    Existing sessions are not affected.

    Args:
        role_id: The role ID to set as current (e.g., 'therapist', 'researcher').
        db: Async database session.
        current_user: The authenticated user.

    Returns:
        UserResponse: The updated user with new current_role_id.

    Raises:
        HTTPException: If the role_id is not found (404).
    """
    # Validate role exists
    if role_id not in PREDEFINED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role '{role_id}' not found",
        )

    # Update user's current role
    current_user.current_role_id = role_id
    await db.commit()
    await db.refresh(current_user)

    return UserResponse.model_validate(current_user)
