from fastapi.responses import JSONResponse

from app.core.exceptions import AppException


def app_error_response(exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
        headers=exc.headers,
    )
