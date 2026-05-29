from __future__ import annotations

import re

from paper_writer_agent.models import ExtractedPaper


_WHITESPACE_RE = re.compile(r"\s+")


def clean_paragraph(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def build_markdown(paper: ExtractedPaper) -> str:
    lines: list[str] = [f"# {clean_paragraph(paper.title)}", ""]

    for section in paper.sections:
        paragraphs = [clean_paragraph(item) for item in section.paragraphs]
        paragraphs = [item for item in paragraphs if item]
        if not paragraphs:
            continue

        lines.append(f"## {clean_paragraph(section.name)}")
        lines.append("")
        for paragraph in paragraphs:
            lines.append(paragraph)
            lines.append("")

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"
