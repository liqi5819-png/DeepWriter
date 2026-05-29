from paper_writer_agent.library import PaperLibrary
from paper_writer_agent.markdown_builder import build_markdown
from paper_writer_agent.models import ExtractedPaper, ExtractedSection, PaperMetadata


def test_library_stores_paper_under_each_keyword_and_searches(tmp_path):
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
    assert (tmp_path / "library" / "immunology" / "paper-1" / "paper.md").exists()
    assert (tmp_path / "library" / "tumor" / "paper-1" / "metadata.json").exists()

    results = library.search("immunotherapy")

    assert len(results) == 1
    assert results[0].paper_id == "paper-1"
    assert results[0].title == "Tumor Immune Microenvironment"
