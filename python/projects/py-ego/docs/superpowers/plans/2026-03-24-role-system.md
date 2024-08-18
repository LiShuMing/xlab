# Role System Integration Plan (Phase 3)

> **Goal:** Integrate the py-ego role system into the FastAPI backend for personalized AI personas.

**Architecture:** Adapt the existing role models from py-ego for database storage and integrate role-specific system prompts into the chat flow.

---

## File Structure

```
py-ego-miniapp/
├── app/
│   ├── core/
│   │   ├── role.py             # Role models (adapted from py-ego)
│   │   └── role_manager.py     # Role management service
│   │
│   ├── models/
│   │   └── user_role.py        # UserRole model for role preferences
│   │
│   ├── services/
│   │   └── role_service.py     # Role business logic
│   │
│   └── api/
│       └── roles.py            # Role API endpoints
```

---

## Task 1: Create Role Models

**Files:**
- Create: `py-ego-miniapp/app/core/role.py`

### Step 1.1: Adapt Role model for backend

Copy the Role model from py-ego/roles/role.py but simplify for API usage:
- Remove file-system dependencies (memory_prefix, profile_filename, etc.)
- Keep: id, name, icon, description, system_prompt, personality, knowledge, examples
- Add: build_full_system_prompt() method

---

## Task 2: Create Role Service

**Files:**
- Create: `py-ego-miniapp/app/services/role_service.py`

### Step 2.1: Create RoleService

```python
class RoleService:
    """Service for managing roles and user role preferences."""

    def get_available_roles(self) -> list[Role]:
        """Return all available roles."""
        return list(PREDEFINED_ROLES.values())

    def get_role(self, role_id: str) -> Role | None:
        """Get a specific role by ID."""
        return PREDEFINED_ROLES.get(role_id)

    def get_system_prompt(self, role_id: str, relationship_context: str = "") -> str:
        """Build the full system prompt for a role."""
        role = self.get_role(role_id)
        if not role:
            return DEFAULT_SYSTEM_PROMPT
        return role.build_full_system_prompt(relationship_context)
```

---

## Task 3: Create Role API

**Files:**
- Create: `py-ego-miniapp/app/api/roles.py`

### Step 3.1: Create role endpoints

```python
@router.get("/", response_model=list[RoleResponse])
async def list_roles() -> list[RoleResponse]:
    """List all available AI roles."""
    ...

@router.get("/{role_id}", response_model=RoleDetailResponse)
async def get_role_detail(role_id: str) -> RoleDetailResponse:
    """Get detailed information about a specific role."""
    ...
```

---

## Task 4: Update Chat Service with Role Support

**Files:**
- Modify: `py-ego-miniapp/app/services/chat_service.py`

### Step 4.1: Integrate role system

Update ChatService to:
1. Get the session's role_id
2. Fetch the role's system prompt
3. Use role-specific prompt in LLM context

---

## Task 5: Update User Model with Current Role

**Files:**
- Modify: `py-ego-miniapp/app/models/user.py`
- Modify: `py-ego-miniapp/app/schemas/user.py`

### Step 5.1: Add current_role field to User

Add `current_role_id` column to User model (default: 'therapist').

---

## Task 6: Create Database Migration

**Files:**
- Create: Alembic migration for user.current_role_id

---

## Task 7: Update Tests

**Files:**
- Create: `py-ego-miniapp/tests/test_roles.py`
- Modify: `py-ego-miniapp/tests/test_chat_api.py` (add role-based tests)

---

## API Endpoints

```
GET  /api/roles              # List all roles
GET  /api/roles/{id}         # Get role details
```

---

## Verification Steps

1. List roles endpoint returns all 4 predefined roles
2. Chat responses use role-specific system prompts
3. Different roles produce different response styles
4. All tests pass
