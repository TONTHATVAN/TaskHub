from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import AuthServiceDep
from app.api.v1.auth_schemas import RegisterRequest, UserRead
from app.domain.user import User
from app.domain.user_repository import EmailAlreadyExistsError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, service: AuthServiceDep) -> User:
    try:
        return await service.register(payload.email, payload.full_name, payload.password)
    except EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail="Email already registered") from exc
