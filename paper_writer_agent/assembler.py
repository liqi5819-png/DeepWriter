from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any

from paper_writer_agent.markdown_builder import clean_paragraph
from paper_writer_agent.models import ExtractedPaper, ExtractedSection


class LocalSectionAssembler:
    def assemble(self, paper_id: str, page_extractions: list[dict[str, Any]]) -> ExtractedPaper:
        title = paper_id
        grouped: OrderedDict[str, list[str]] = OrderedDict()
        source_pages: dict[str, list[int]] = {}

        for extraction in sorted(page_extractions, key=lambda item: int(item.get("page", 0))):
            page_number = int(extraction.get("page", 0))
            for section in extraction.get("sections", []):
                name = clean_paragraph(str(section.get("name") or "Body"))
                paragraphs = [_normalize_paragraph(item) for item in section.get("paragraphs", [])]
                paragraphs = [item for item in paragraphs if item]
                if not name or not paragraphs:
                    continue
                if name.casefold() == "title":
                    title = paragraphs[0]
                    continue
                if name not in grouped:
                    grouped[name] = []
                    source_pages[name] = []
                _extend_paragraphs(grouped[name], paragraphs)
                pages = section.get("source_pages") or [page_number]
                for page in pages:
                    page_int = int(page)
                    if page_int not in source_pages[name]:
                        source_pages[name].append(page_int)

        sections = [
            ExtractedSection(
                name=name,
                paragraphs=paragraphs,
                source_pages=source_pages.get(name, []),
            )
            for name, paragraphs in grouped.items()
        ]
        return ExtractedPaper(paper_id=paper_id, title=title, sections=sections)


def paper_from_json(data: dict[str, Any]) -> ExtractedPaper:
    return ExtractedPaper(
        paper_id=str(data.get("paper_id", "")),
        title=str(data.get("title", "")),
        sections=[
            ExtractedSection(
                name=str(section.get("name", "")),
                paragraphs=[str(item) for item in section.get("paragraphs", [])],
                source_pages=[int(page) for page in section.get("source_pages", [])],
            )
            for section in data.get("sections", [])
        ],
    )


def _extend_paragraphs(existing: list[str], incoming: list[str]) -> None:
    for paragraph in incoming:
        if existing and _looks_like_continuation(existing[-1], paragraph):
            existing[-1] = _join_split_paragraph(existing[-1], paragraph)
        else:
            existing.append(paragraph)


def _normalize_paragraph(value: Any) -> str:
    text = str(value).replace("\r", "\n")
    text = re.sub(r"\s*\n\s*", " ", text)
    return clean_paragraph(text)


def _looks_like_continuation(previous: str, current: str) -> bool:
    if previous.endswith("-"):
        return True
    return bool(previous) and bool(current) and previous[-1] not in ".?!:;"


def _join_split_paragraph(previous: str, current: str) -> str:
    if previous.endswith("-"):
        return clean_paragraph(previous[:-1] + current)
    return clean_paragraph(previous + " " + current)
