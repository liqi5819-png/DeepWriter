from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from paper_writer_agent.assembler import LocalSectionAssembler, paper_from_json
from paper_writer_agent.markdown_builder import build_markdown
from paper_writer_agent.models import (
    AuditReport,
    ExtractedPaper,
    ExtractedSection,
    PageArtifact,
    PipelineResult,
    TARGET_SECTIONS,
    to_jsonable,
)


class Preprocessor(Protocol):
    def preprocess(self, pdf_path: Path, paper_id: str) -> list[PageArtifact]:
        pass


class LLMProvider(Protocol):
    def extract_page(self, page: PageArtifact, target_sections: tuple[str, ...]) -> dict:
        pass

    def assemble_paper(self, paper_id: str, page_extractions: list[dict]) -> ExtractedPaper:
        pass

    def audit_extraction(
        self,
        paper: ExtractedPaper,
        pages: list[PageArtifact],
        page_extractions: list[dict],
    ) -> AuditReport:
        pass

    def repair_extraction(
        self,
        issue: dict,
        pages: list[PageArtifact],
        current_paper: ExtractedPaper,
    ) -> ExtractedPaper:
        pass


class ExtractionPipeline:
    def __init__(
        self,
        preprocessor: Preprocessor,
        llm_provider: LLMProvider,
        work_dir: Path,
        max_repair_rounds: int = 1,
        assembler: LocalSectionAssembler | None = None,
    ):
        self.preprocessor = preprocessor
        self.llm_provider = llm_provider
        self.work_dir = work_dir
        self.max_repair_rounds = max_repair_rounds
        self.assembler = assembler or LocalSectionAssembler()

    def extract(self, pdf_path: Path, paper_id: str) -> PipelineResult:
        run_dir = self.work_dir / paper_id
        run_dir.mkdir(parents=True, exist_ok=True)
        page_extractions_path = run_dir / "page_extractions.json"
        assembled_path = run_dir / "assembled_paper.json"
        quality_path = run_dir / "quality_report.json"
        markdown_path = run_dir / "paper.final.md"

        cached = self._load_complete_cache(
            page_extractions_path=page_extractions_path,
            assembled_path=assembled_path,
            quality_path=quality_path,
        )
        if cached:
            paper, page_extractions, report = cached
            markdown = build_markdown(paper)
            if not markdown_path.exists():
                markdown_path.write_text(markdown, encoding="utf-8")
            return PipelineResult(
                paper=paper,
                markdown=markdown,
                quality_report=report,
                page_extractions=page_extractions,
            )

        pages = self.preprocessor.preprocess(pdf_path, paper_id)
        page_extractions = self._extract_pages_with_cache(pages, page_extractions_path)
        paper = self.assembler.assemble(paper_id, page_extractions)
        assembled_path.write_text(
            json.dumps(to_jsonable(paper), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report = self._audit_by_section(paper, pages, page_extractions)

        rounds = 0
        while report.repair_required and rounds < self.max_repair_rounds:
            rounds += 1
            for issue in report.issues:
                paper = self.llm_provider.repair_extraction(issue, pages, paper)
            (run_dir / f"assembled_paper.repair_{rounds}.json").write_text(
                json.dumps(to_jsonable(paper), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            report = self._audit_by_section(paper, pages, page_extractions)

        markdown = build_markdown(paper)
        assembled_path.write_text(
            json.dumps(to_jsonable(paper), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        quality_path.write_text(
            json.dumps(to_jsonable(report), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        markdown_path.write_text(markdown, encoding="utf-8")
        return PipelineResult(
            paper=paper,
            markdown=markdown,
            quality_report=report,
            page_extractions=page_extractions,
        )

    def _extract_pages_with_cache(
        self,
        pages: list[PageArtifact],
        cache_path: Path,
    ) -> list[dict[str, Any]]:
        cached = _load_json_list(cache_path)
        by_page = {int(item["page"]): item for item in cached if "page" in item}

        for page in pages:
            if page.page_number in by_page:
                continue
            by_page[page.page_number] = self.llm_provider.extract_page(page, TARGET_SECTIONS)
            cache_path.write_text(
                json.dumps([by_page[index] for index in sorted(by_page)], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        ordered = [by_page[page.page_number] for page in pages if page.page_number in by_page]
        cache_path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")
        return ordered

    def _audit_by_section(
        self,
        paper: ExtractedPaper,
        pages: list[PageArtifact],
        page_extractions: list[dict[str, Any]],
    ) -> AuditReport:
        if not paper.sections:
            return AuditReport(
                complete=False,
                repair_required=True,
                issues=[
                    {
                        "type": "missing_sections",
                        "section": "all",
                        "pages": [page.page_number for page in pages],
                        "reason": "No readable target sections were assembled.",
                    }
                ],
            )

        reports = [
            self._audit_one_section(paper, section, pages, page_extractions)
            for section in paper.sections
        ]
        issues: list[dict[str, Any]] = []
        notes: list[str] = []
        for report in reports:
            issues.extend(report.issues)
            notes.extend(report.notes)
        return AuditReport(
            complete=all(report.complete for report in reports) and not issues,
            repair_required=any(report.repair_required for report in reports),
            issues=issues,
            notes=notes,
        )

    def _audit_one_section(
        self,
        paper: ExtractedPaper,
        section: ExtractedSection,
        pages: list[PageArtifact],
        page_extractions: list[dict[str, Any]],
    ) -> AuditReport:
        audit_section = getattr(self.llm_provider, "audit_section", None)
        relevant_pages = _pages_for_section(section, pages)
        if audit_section:
            return audit_section(paper, section, relevant_pages, page_extractions)
        return self.llm_provider.audit_extraction(paper, relevant_pages, page_extractions)

    def _load_complete_cache(
        self,
        page_extractions_path: Path,
        assembled_path: Path,
        quality_path: Path,
    ) -> tuple[ExtractedPaper, list[dict[str, Any]], AuditReport] | None:
        if not (
            page_extractions_path.exists()
            and assembled_path.exists()
            and quality_path.exists()
        ):
            return None
        page_extractions = _load_json_list(page_extractions_path)
        paper_path = _latest_assembled_path(assembled_path)
        paper = paper_from_json(json.loads(paper_path.read_text(encoding="utf-8")))
        report_data = json.loads(quality_path.read_text(encoding="utf-8"))
        report = AuditReport(
            complete=bool(report_data.get("complete")),
            repair_required=bool(report_data.get("repair_required")),
            issues=list(report_data.get("issues", [])),
            notes=list(report_data.get("notes", [])),
        )
        return paper, page_extractions, report


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")))


def _pages_for_section(section: ExtractedSection, pages: list[PageArtifact]) -> list[PageArtifact]:
    page_numbers = set(section.source_pages)
    selected = [page for page in pages if page.page_number in page_numbers]
    return selected or pages


def _latest_assembled_path(assembled_path: Path) -> Path:
    repair_paths = sorted(
        assembled_path.parent.glob("assembled_paper.repair_*.json"),
        key=lambda path: int(path.stem.rsplit("_", 1)[-1]),
    )
    return repair_paths[-1] if repair_paths else assembled_path
