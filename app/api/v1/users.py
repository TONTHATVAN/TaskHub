from fastapi import APIRouter, Response, status

from app.api.dependencies import CurrentUserDep, ProfileServiceDep
from app.api.exceptions import (
    EmailAlreadyRegisteredException,
    IncorrectCurrentPasswordException,
)
from app.api.v1.auth_schemas import (
    ChangePasswordRequest,
    ProfileUpdateRequest,
    UserRead,
)
from app.application.profile_service import IncorrectPasswordError
from app.domain.user import User
from app.domain.user_repository import EmailAlreadyExistsError

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_me(user: CurrentUserDep) -> User:
    return user


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: ProfileUpdateRequest, user: CurrentUserDep, service: ProfileServiceDep
) -> User:
    try:
        return await service.update(user, payload.to_changes())
    except EmailAlreadyExistsError as exc:
        raise EmailAlreadyRegisteredException() from exc


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest, user: CurrentUserDep, service: ProfileServiceDep
) -> Response:
    try:
        await service.change_password(
            user, payload.current_password, payload.new_password
        )
    except IncorrectPasswordError as exc:
        raise IncorrectCurrentPasswordException() from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
