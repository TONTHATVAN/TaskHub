from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    email: str
    full_name: str
    hashed_password: str
    role: UserRole
    is_active: bool
    created_at: datetime
