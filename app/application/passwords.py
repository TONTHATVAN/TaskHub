import asyncio

import bcrypt

from app.core.constants import PASSWORD_MAX_BYTES
from app.core.messages import PASSWORD_TOO_LONG_MESSAGE


async def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > PASSWORD_MAX_BYTES:
        raise ValueError(PASSWORD_TOO_LONG_MESSAGE)
    return await asyncio.to_thread(
        lambda: bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("ascii")
    )


async def verify_password(password: str, hashed_password: str) -> bool:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > PASSWORD_MAX_BYTES:
        return False
    try:
        return await asyncio.to_thread(
            bcrypt.checkpw, password_bytes, hashed_password.encode("ascii")
        )
    except (UnicodeEncodeError, ValueError):
        return False
