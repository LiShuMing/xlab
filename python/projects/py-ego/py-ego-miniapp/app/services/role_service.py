"""Role service for managing AI personas.

This module provides business logic for role management and system prompt generation.
"""
from __future__ import annotations

from app.core.role import PREDEFINED_ROLES, Role


class RoleService:
    """Service for managing roles and user role preferences."""

    def get_available_roles(self) -> list[Role]:
        """Return all available roles.

        Returns:
            List of all predefined roles.
        """
        return list(PREDEFINED_ROLES.values())

    def get_role(self, role_id: str) -> Role | None:
        """Get a specific role by ID.

        Args:
            role_id: The unique identifier for the role.

        Returns:
            The Role if found, None otherwise.
        """
        return PREDEFINED_ROLES.get(role_id)

    def get_system_prompt(self, role_id: str, relationship_context: str = "") -> str:
        """Build the full system prompt for a role.

        Args:
            role_id: The unique identifier for the role.
            relationship_context: Optional relationship memory context to include.

        Returns:
            The complete system prompt for the LLM, or a default prompt if role not found.
        """
        role = self.get_role(role_id)
        if not role:
            return self._get_default_system_prompt()
        return role.build_full_system_prompt(relationship_context)

    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt when no role is specified.

        Returns:
            A generic helpful assistant prompt.
        """
        return (
            "你是一位 helpful AI assistant。"
            "你会认真倾听用户的问题，并提供清晰、准确、有用的回答。"
        )


# Global service instance
role_service = RoleService()
