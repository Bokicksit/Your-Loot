from pydantic import BaseModel, ConfigDict


class OwnedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    condition: str | None = None
    sleeve_condition: str | None = None  # records: sleeve grade
    completeness: str | None = None
    grader: str | None = None  # cards: PSA/BGS/CGC/… (null = raw)
    grade: str | None = None
    in_binder: bool = False  # cards: this copy occupies a binder slot
    variant: str | None = None  # cards: Non-Holo/Reverse Holo/Holo
    stamp: str | None = None  # cards: promo stamp text
    notes: str | None = None


class OwnedCreate(BaseModel):
    condition: str | None = None
    sleeve_condition: str | None = None  # records only
    completeness: str | None = None  # games only
    grader: str | None = None  # cards only
    grade: str | None = None
    in_binder: bool = False  # cards only
    variant: str | None = None  # cards only
    stamp: str | None = None  # cards only
    notes: str | None = None


class WantedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    priority: int | None = None
    notes: str | None = None


class WantedCreate(BaseModel):
    priority: int | None = None
    notes: str | None = None
