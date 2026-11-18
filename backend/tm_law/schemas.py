from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
Key = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")]
PassageText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)
]
Kind = Literal["predpis", "rozhodnutie", "eu", "iný"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Passage(StrictModel):
    source_id: Key
    section: Short | None = None
    paragraph: Short | None = None
    letter: Short | None = None
    text: PassageText


class LegalVersion(StrictModel):
    version_id: Key
    title: Short
    kind: Kind
    law_number: Annotated[int, Field(ge=1)] | None = None
    law_year: Annotated[int, Field(ge=1000, le=9999)] | None = None
    authority: Short
    source_url: HttpUrl | None = None
    acquired_on: date
    published_on: date | None = None
    effective_from: date | None = None
    effective_until: date | None = None
    open_ended: bool = False
    case_number: Short | None = None
    decision_date: date | None = None
    provenance: Short
    reuse_terms: Short
    fictional: bool = False
    original_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")] | None = None
    passages: Annotated[list[Passage], Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def consistent_metadata(self):
        if not self.fictional and self.source_url is None:
            raise ValueError("Pre skutočný zdroj vyplňte zdrojovú URL.")
        if (self.law_number is None) != (self.law_year is None):
            raise ValueError("Číslo a rok predpisu zadajte spolu.")
        if self.open_ended and (self.effective_from is None or self.effective_until is not None):
            raise ValueError("Otvorený interval vyžaduje začiatok a nemôže mať koniec.")
        if self.effective_until and (
            not self.effective_from or self.effective_until <= self.effective_from
        ):
            raise ValueError("Koniec účinnosti musí byť po začiatku.")
        if len({p.source_id for p in self.passages}) != len(self.passages):
            raise ValueError("Identifikátory úsekov musia byť jedinečné v rámci znenia.")
        return self


class RuntimeOptions(StrictModel):
    model: Annotated[Short, StringConstraints(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]*$")] | None = (
        None
    )
    context_window: Annotated[int, Field(ge=2048, le=32768)] = 4096
    temperature: Annotated[float, Field(ge=0, le=1)] = 0.15
    max_tokens: Annotated[int, Field(ge=64, le=2048)] = 768


class ChatInput(StrictModel):
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=3, max_length=4000)
    ]
    query: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
        | None
    ) = None
    as_of: date | None = None
    document_id: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")] | None = None
    options: RuntimeOptions = Field(default_factory=RuntimeOptions)

    @model_validator(mode="after")
    def context_budget(self):
        if self.options.max_tokens > self.options.context_window // 2:
            raise ValueError("Limit odpovede nesmie presiahnuť polovicu kontextu.")
        return self
