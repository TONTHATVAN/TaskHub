from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Label:
    id: UUID
    project_id: UUID
    name: str
    color: str
