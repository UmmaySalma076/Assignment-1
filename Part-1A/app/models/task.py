from dataclasses import dataclass


@dataclass(slots=True)
class Task:
    id: int
    title: str
    description: str | None
    completed: bool
    created_at: str
