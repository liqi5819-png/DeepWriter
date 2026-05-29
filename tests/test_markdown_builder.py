from paper_writer_agent.markdown_builder import build_markdown
from paper_writer_agent.models import ExtractedPaper, ExtractedSection


def test_build_markdown_outputs_clean_sections():
    paper = ExtractedPaper(
        paper_id="demo",
        title="  Example   Study  ",
        sections=[
            ExtractedSection(
                name="Abstract",
                paragraphs=["First line\ncontinues with  extra   spaces.", "", "Second paragraph."],
                source_pages=[1],
            ),
            ExtractedSection(
                name="Results",
                paragraphs=["Result paragraph."],
                source_pages=[3],
            ),
        ],
    )

    markdown = build_markdown(paper)

    assert markdown == (
        "# Example Study\n\n"
        "## Abstract\n\n"
        "First line continues with extra spaces.\n\n"
        "Second paragraph.\n\n"
        "## Results\n\n"
        "Result paragraph.\n"
    )
