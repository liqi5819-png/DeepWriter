from __future__ import annotations

import json
from pathlib import Path

from paper_writer_agent.models import ExtractedPaper, PaperMetadata, StoredPaper, to_jsonable


class PaperLibrary:
    def __init__(self, root: Path):
        self.root = root

    def store_paper(
        self,
        paper: ExtractedPaper,
        markdown: str,
        metadata: PaperMetadata,
        quality_report: dict,
    ) -> StoredPaper:
        if not metadata.keywords:
            raise ValueError("At least one keyword is required to store a paper.")

        self.root.mkdir(parents=True, exist_ok=True)
        paper_md = self.root / f"{_slug(paper.paper_id)}.md"
        content = _with_front_matter(markdown, metadata, quality_report)
        paper_md.write_text(content, encoding="utf-8")

        return StoredPaper(
            paper_id=paper.paper_id,
            title=paper.title,
            keywords=metadata.keywords,
            paper_md=paper_md,
            metadata_json=paper_md,
            quality_report_json=paper_md,
        )

    def search(self, query: str) -> list[StoredPaper]:
        query_terms = [term.casefold() for term in query.split() if term.strip()]
        results: dict[str, StoredPaper] = {}

        for paper_md in self.root.glob("*.md"):
            text = paper_md.read_text(encoding="utf-8")
            metadata = _parse_front_matter(text)
            haystack = text.casefold()

            if query_terms and not any(term in haystack for term in query_terms):
                continue

            paper_id = metadata.get("paper_id") or paper_md.stem
            results[paper_id] = StoredPaper(
                paper_id=paper_id,
                title=metadata.get("title", ""),
                keywords=_split_csv(metadata.get("keywords", "")),
                paper_md=paper_md,
                metadata_json=paper_md,
                quality_report_json=paper_md,
            )

        return sorted(results.values(), key=lambda item: item.title.casefold())


def _slug(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    parts = [part for part in cleaned.split("-") if part]
    return "-".join(parts) or "unknown"


def _with_front_matter(markdown: str, metadata: PaperMetadata, quality_report: dict) -> str:
    quality = to_jsonable(quality_report)
    lines = [
        "---",
        f"paper_id: {metadata.paper_id}",
        f"title: {metadata.title}",
        f"keywords: {', '.join(metadata.keywords)}",
        f"source_pdf: {metadata.source_pdf}",
        f"quality_complete: {str(bool(quality.get('complete'))).lower()}",
        f"repair_required: {str(bool(quality.get('repair_required'))).lower()}",
        f"quality_issues: {len(quality.get('issues', []))}",
        f"quality_report_json: {json.dumps(quality, ensure_ascii=False)}",
        "---",
        "",
    ]
    return "\n".join(lines) + markdown.lstrip()


def _parse_front_matter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    metadata: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
