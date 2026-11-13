from typing import Generic, TypeVar

from pydantic import BaseModel

ItemT = TypeVar("ItemT")


class PageRead(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    total: int
    page: int
    limit: int
