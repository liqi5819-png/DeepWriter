from paper_writer_agent.library import PaperLibrary
from paper_writer_agent.markdown_builder import build_markdown
from paper_writer_agent.models import ExtractedPaper, ExtractedSection, PaperMetadata


def test_library_stores_single_markdown_with_front_matter_and_searches(tmp_path):
    library = PaperLibrary(tmp_path / "library")
    paper = ExtractedPaper(
        paper_id="paper-1",
        title="Tumor Immune Microenvironment",
        sections=[
            ExtractedSection(
                name="Introduction",
                paragraphs=["Tumor immune microenvironment shapes immunotherapy response."],
                source_pages=[1],
            )
        ],
    )
    metadata = PaperMetadata(
        paper_id="paper-1",
        title=paper.title,
        keywords=["immunology", "tumor"],
        source_pdf="paper.pdf",
    )

    stored = library.store_paper(
        paper=paper,
        markdown=build_markdown(paper),
        metadata=metadata,
        quality_report={"complete": True, "issues": []},
    )

    assert stored.paper_md.exists()
    assert stored.paper_md == tmp_path / "library" / "paper-1.md"
    assert not (tmp_path / "library" / "immunology").exists()

    stored_text = stored.paper_md.read_text(encoding="utf-8")
    assert "keywords: immunology, tumor" in stored_text
    assert "quality_complete: true" in stored_text
    assert "# Tumor Immune Microenvironment" in stored_text

    results = library.search("immunotherapy")

    assert len(results) == 1
    assert results[0].paper_id == "paper-1"
    assert results[0].title == "Tumor Immune Microenvironment"
