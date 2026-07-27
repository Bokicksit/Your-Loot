from pydantic import BaseModel, ConfigDict


class OwnedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    condition: str | None = None
    completeness: str | None = None
    grader: str | None = None  # cards: PSA/BGS/CGC/… (null = raw)
    grade: str | None = None
    notes: str | None = None


class OwnedCreate(BaseModel):
    condition: str | None = None
    completeness: str | None = None  # games only
    grader: str | None = None  # cards only
    grade: str | None = None
    notes: str | None = None


class WantedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    priority: int | None = None
    notes: str | None = None


class WantedCreate(BaseModel):
    priority: int | None = None
    notes: str | None = None
