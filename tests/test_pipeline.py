from pathlib import Path

from paper_writer_agent.models import AuditReport, ExtractedPaper, ExtractedSection, PageArtifact
from paper_writer_agent.pipeline import ExtractionPipeline


class FakePreprocessor:
    def preprocess(self, pdf_path: Path, paper_id: str):
        return [
            PageArtifact(
                page_number=1,
                image_path=Path("page_001.png"),
                text_path=Path("page_001.txt"),
                raw_text="Abstract text on page 1.",
            )
        ]


class RepairingProvider:
    def __init__(self):
        self.audit_calls = 0
        self.audit_section_calls = []
        self.assemble_calls = 0
        self.repair_calls = 0

    def extract_page(self, page, target_sections):
        return {
            "page": page.page_number,
            "sections": [
                {
                    "name": "Abstract",
                    "paragraphs": ["Broken abstract"],
                    "source_pages": [1],
                }
            ],
            "excluded_content": [],
        }

    def assemble_paper(self, paper_id, page_extractions):
        self.assemble_calls += 1
        raise AssertionError("Pipeline should assemble locally instead of calling the LLM.")

    def audit_section(self, paper, section, pages, page_extractions):
        self.audit_section_calls.append(section.name)
        self.audit_calls += 1
        if self.audit_calls == 1:
            return AuditReport(
                complete=False,
                repair_required=True,
                issues=[
                    {
                        "type": "incomplete_paragraph",
                        "section": section.name,
                        "pages": [1],
                        "reason": "The abstract is truncated.",
                    }
                ],
            )
        return AuditReport(complete=True, repair_required=False, issues=[])

    def audit_extraction(self, paper, pages, page_extractions):
        self.audit_calls += 1
        if self.audit_calls == 1:
            return AuditReport(
                complete=False,
                repair_required=True,
                issues=[
                    {
                        "type": "incomplete_paragraph",
                        "section": "Abstract",
                        "pages": [1],
                        "reason": "The abstract is truncated.",
                    }
                ],
            )
        return AuditReport(complete=True, repair_required=False, issues=[])

    def repair_extraction(self, issue, pages, current_paper):
        self.repair_calls += 1
        return ExtractedPaper(
            paper_id=current_paper.paper_id,
            title=current_paper.title,
            sections=[
                ExtractedSection(
                    name="Abstract",
                    paragraphs=["Repaired abstract text on page 1."],
                    source_pages=[1],
                )
            ],
        )


def test_pipeline_runs_repair_when_audit_finds_incomplete_extraction(tmp_path):
    provider = RepairingProvider()
    pipeline = ExtractionPipeline(
        preprocessor=FakePreprocessor(),
        llm_provider=provider,
        work_dir=tmp_path,
    )

    result = pipeline.extract(pdf_path=Path("demo.pdf"), paper_id="demo")

    assert provider.repair_calls == 1
    assert provider.assemble_calls == 0
    assert provider.audit_section_calls == ["Abstract", "Abstract"]
    assert result.quality_report.complete is True
    assert result.paper.sections[0].paragraphs == ["Repaired abstract text on page 1."]


class CountingProvider:
    def __init__(self):
        self.extract_calls = 0

    def extract_page(self, page, target_sections):
        self.extract_calls += 1
        return {
            "page": page.page_number,
            "sections": [
                {
                    "name": "Abstract",
                    "paragraphs": [f"Extracted page {page.page_number}"],
                    "source_pages": [page.page_number],
                }
            ],
            "excluded_content": [],
        }

    def audit_section(self, paper, section, pages, page_extractions):
        return AuditReport(complete=True, repair_required=False, issues=[])

    def repair_extraction(self, issue, pages, current_paper):
        return current_paper


def test_pipeline_caches_page_extractions_between_runs(tmp_path):
    provider = CountingProvider()
    pipeline = ExtractionPipeline(
        preprocessor=FakePreprocessor(),
        llm_provider=provider,
        work_dir=tmp_path,
    )

    first = pipeline.extract(pdf_path=Path("demo.pdf"), paper_id="demo")
    second = pipeline.extract(pdf_path=Path("demo.pdf"), paper_id="demo")

    assert provider.extract_calls == 1
    assert first.page_extractions == second.page_extractions
    assert (tmp_path / "demo" / "page_extractions.json").exists()
    assert (tmp_path / "demo" / "assembled_paper.json").exists()
    assert (tmp_path / "demo" / "quality_report.json").exists()
