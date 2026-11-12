from typing import Any
from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str | None = None
    is_active: bool
    is_admin: bool
    mfa_enabled: bool = False
    created_at: Any

    model_config = {"from_attributes": True}
