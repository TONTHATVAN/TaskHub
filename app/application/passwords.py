import asyncio

import bcrypt


async def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError("Password must be at most 72 bytes")
    return await asyncio.to_thread(
        lambda: bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("ascii")
    )


async def verify_password(password: str, hashed_password: str) -> bool:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        return False
    return await asyncio.to_thread(
        bcrypt.checkpw, password_bytes, hashed_password.encode("ascii")
    )
