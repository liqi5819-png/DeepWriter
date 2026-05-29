from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


TARGET_SECTIONS = (
    "Title",
    "Abstract",
    "Introduction",
    "Materials and Methods",
    "Results",
    "Discussion",
)


@dataclass(slots=True)
class PageArtifact:
    page_number: int
    image_path: Path
    text_path: Path
    raw_text: str = ""


@dataclass(slots=True)
class ExtractedSection:
    name: str
    paragraphs: list[str]
    source_pages: list[int] = field(default_factory=list)


@dataclass(slots=True)
class ExtractedPaper:
    paper_id: str
    title: str
    sections: list[ExtractedSection]


@dataclass(slots=True)
class AuditReport:
    complete: bool
    repair_required: bool
    issues: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PaperMetadata:
    paper_id: str
    title: str
    keywords: list[str]
    source_pdf: str
    authors: list[str] = field(default_factory=list)
    year: str | None = None
    doi: str | None = None


@dataclass(slots=True)
class StoredPaper:
    paper_id: str
    title: str
    keywords: list[str]
    paper_md: Path
    metadata_json: Path
    quality_report_json: Path


@dataclass(slots=True)
class PipelineResult:
    paper: ExtractedPaper
    markdown: str
    quality_report: AuditReport
    page_extractions: list[dict[str, Any]]


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "__dataclass_fields__"):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value
