from __future__ import annotations

import json
import shutil
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

        primary_dir = self._paper_dir(metadata.keywords[0], paper.paper_id)
        primary_dir.mkdir(parents=True, exist_ok=True)
        paper_md = primary_dir / "paper.md"
        metadata_json = primary_dir / "metadata.json"
        quality_report_json = primary_dir / "quality_report.json"

        paper_md.write_text(markdown, encoding="utf-8")
        metadata_json.write_text(
            json.dumps(to_jsonable(metadata), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        quality_report_json.write_text(
            json.dumps(to_jsonable(quality_report), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        for keyword in metadata.keywords[1:]:
            alias_dir = self._paper_dir(keyword, paper.paper_id)
            if alias_dir.exists():
                shutil.rmtree(alias_dir)
            shutil.copytree(primary_dir, alias_dir)

        return StoredPaper(
            paper_id=paper.paper_id,
            title=paper.title,
            keywords=metadata.keywords,
            paper_md=paper_md,
            metadata_json=metadata_json,
            quality_report_json=quality_report_json,
        )

    def search(self, query: str) -> list[StoredPaper]:
        query_terms = [term.casefold() for term in query.split() if term.strip()]
        results: dict[str, StoredPaper] = {}

        for metadata_path in self.root.glob("*/*/metadata.json"):
            paper_dir = metadata_path.parent
            paper_md = paper_dir / "paper.md"
            quality_report = paper_dir / "quality_report.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            text = paper_md.read_text(encoding="utf-8") if paper_md.exists() else ""
            haystack = " ".join(
                [
                    metadata.get("title", ""),
                    " ".join(metadata.get("keywords", [])),
                    text,
                ]
            ).casefold()

            if query_terms and not any(term in haystack for term in query_terms):
                continue

            results[metadata["paper_id"]] = StoredPaper(
                paper_id=metadata["paper_id"],
                title=metadata.get("title", ""),
                keywords=metadata.get("keywords", []),
                paper_md=paper_md,
                metadata_json=metadata_path,
                quality_report_json=quality_report,
            )

        return sorted(results.values(), key=lambda item: item.title.casefold())

    def _paper_dir(self, keyword: str, paper_id: str) -> Path:
        return self.root / _slug(keyword) / _slug(paper_id)


def _slug(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    parts = [part for part in cleaned.split("-") if part]
    return "-".join(parts) or "unknown"
