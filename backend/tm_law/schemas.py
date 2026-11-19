from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
Key = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")]
PassageText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)
]
Reasoning = Literal["auto", "on", "off"]
Kind = Literal["predpis", "rozhodnutie", "eu", "iný"]
OLLAMA_THREAD_LIMIT = 256


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Passage(StrictModel):
    source_id: Key
    section: Short | None = None
    paragraph: Short | None = None
    letter: Short | None = None
    text: PassageText
    norm_status: Literal["in_force", "repealed", "transitional", "unknown"] | None = None


class LegalVersion(StrictModel):
    version_id: Key
    title: Short
    kind: Kind
    law_number: Annotated[int, Field(ge=1)] | None = None
    law_year: Annotated[int, Field(ge=1000, le=9999)] | None = None
    authority: Short
    source_url: HttpUrl | None = None
    acquired_on: date
    acquired_at: datetime | None = None
    published_on: date | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    effective_from: date | None = None
    effective_until: date | None = None
    effective_basis: Short | None = None
    open_ended: bool = False
    case_number: Short | None = None
    decision_date: date | None = None
    decision_type: Short | None = None
    publication_status: Literal["published", "anonymized", "unknown"] | None = None
    cited_legislation: Annotated[list[Short], Field(max_length=100)] | None = None
    provenance: Short
    reuse_terms: Short
    fictional: bool = False
    original_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")] | None = None
    # One pinned Slov-Lex wording can exceed the earlier 500-passage cap.
    passages: Annotated[list[Passage], Field(min_length=1, max_length=800)]

    @model_validator(mode="after")
    def consistent_metadata(self):
        if not self.fictional and self.source_url is None:
            raise ValueError("Pre skutočný zdroj vyplňte zdrojovú URL.")
        if (self.law_number is None) != (self.law_year is None):
            raise ValueError("Číslo a rok predpisu zadajte spolu.")
        if self.acquired_at and (
            self.acquired_at.utcoffset() is None or self.acquired_at.date() != self.acquired_on
        ):
            raise ValueError("Čas získania musí obsahovať posun UTC a zhodný dátum získania.")
        if self.valid_until and self.valid_from and self.valid_until <= self.valid_from:
            raise ValueError("Koniec platnosti musí byť po začiatku.")
        if self.open_ended and (self.effective_from is None or self.effective_until is not None):
            raise ValueError("Otvorený interval vyžaduje začiatok a nemôže mať koniec.")
        if self.effective_until and (
            not self.effective_from or self.effective_until <= self.effective_from
        ):
            raise ValueError("Koniec účinnosti musí byť po začiatku.")
        if len({p.source_id for p in self.passages}) != len(self.passages):
            raise ValueError("Identifikátory úsekov musia byť jedinečné v rámci znenia.")
        if self.kind == "rozhodnutie" and not all(
            (self.case_number, self.decision_date, self.decision_type, self.publication_status)
        ):
            raise ValueError("Rozhodnutie vyžaduje spisovú značku, dátum, typ a stav publikovania.")
        return self


class RuntimeOptions(StrictModel):
    model: Annotated[Short, StringConstraints(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]*$")] | None = (
        None
    )
    context_window: Annotated[int, Field(ge=2048, le=32768)] = 4096
    temperature: Annotated[float, Field(ge=0, le=1)] = 0.15
    max_tokens: Annotated[int, Field(ge=64, le=8192)] = 768
    reasoning: Reasoning = "auto"
    measure_memory: bool = False
    device: Literal["auto", "cpu"] = "auto"
    seed: Annotated[int, Field(ge=0, le=2147483647)] | None = None
    cpu_threads: Annotated[int, Field(ge=1, le=OLLAMA_THREAD_LIMIT)] | None = None


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
