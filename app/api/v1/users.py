from fastapi import APIRouter, HTTPException, Response, status

from app.api.dependencies import CurrentUserDep, ProfileServiceDep
from app.api.v1.auth_constants import EMAIL_ALREADY_REGISTERED_MESSAGE
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
        return await service.update(
            user,
            email=payload.email if payload.email is not None else user.email,
            full_name=payload.full_name
            if payload.full_name is not None
            else user.full_name,
        )
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409, detail=EMAIL_ALREADY_REGISTERED_MESSAGE
        ) from exc


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest, user: CurrentUserDep, service: ProfileServiceDep
) -> Response:
    try:
        await service.change_password(
            user, payload.current_password, payload.new_password
        )
    except IncorrectPasswordError as exc:
        raise HTTPException(
            status_code=400, detail="Current password is incorrect"
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
