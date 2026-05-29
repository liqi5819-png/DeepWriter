from paper_writer_agent.assembler import LocalSectionAssembler


def test_local_assembler_merges_page_extractions_without_llm_call():
    page_extractions = [
        {
            "page": 1,
            "sections": [
                {
                    "name": "Title",
                    "paragraphs": ["Example Paper"],
                    "source_pages": [1],
                },
                {
                    "name": "Abstract",
                    "paragraphs": ["This is hyphen-", "ated text."],
                    "source_pages": [1],
                },
            ],
        },
        {
            "page": 2,
            "sections": [
                {
                    "name": "Introduction",
                    "paragraphs": ["First paragraph.\nSecond line."],
                    "source_pages": [2],
                }
            ],
        },
    ]

    paper = LocalSectionAssembler().assemble("paper-1", page_extractions)

    assert paper.title == "Example Paper"
    assert [section.name for section in paper.sections] == ["Abstract", "Introduction"]
    assert paper.sections[0].paragraphs == ["This is hyphenated text."]
    assert paper.sections[1].paragraphs == ["First paragraph. Second line."]
