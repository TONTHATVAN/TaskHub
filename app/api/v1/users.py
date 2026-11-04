from fastapi import APIRouter

from app.api.dependencies import CurrentUserDep
from app.api.v1.auth_schemas import UserRead
from app.domain.user import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_me(user: CurrentUserDep) -> User:
    return user
