from __future__ import annotations

import base64
import json
import mimetypes
import re
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

from paper_writer_agent.models import AuditReport, ExtractedPaper, ExtractedSection, PageArtifact


class MockLLMProvider:
    """Local provider for testing the pipeline before real API credentials are wired."""

    def extract_page(self, page: PageArtifact, target_sections: tuple[str, ...]) -> dict[str, Any]:
        paragraphs = [
            line.strip()
            for line in page.raw_text.splitlines()
            if line.strip() and not _looks_like_non_body(line)
        ]
        section_name = _guess_section(page.raw_text, target_sections)
        return {
            "page": page.page_number,
            "sections": [
                {
                    "name": section_name,
                    "paragraphs": paragraphs or [f"Mock extraction for page {page.page_number}."],
                    "source_pages": [page.page_number],
                }
            ],
            "excluded_content": [],
        }

    def assemble_paper(self, paper_id: str, page_extractions: list[dict[str, Any]]) -> ExtractedPaper:
        grouped: dict[str, list[str]] = defaultdict(list)
        source_pages: dict[str, list[int]] = defaultdict(list)
        title = paper_id

        for extraction in page_extractions:
            for section in extraction.get("sections", []):
                name = section.get("name", "Body")
                if name.casefold() == "title" and section.get("paragraphs"):
                    title = section["paragraphs"][0]
                    continue
                grouped[name].extend(section.get("paragraphs", []))
                source_pages[name].extend(section.get("source_pages", [extraction.get("page")]))

        sections = [
            ExtractedSection(name=name, paragraphs=paragraphs, source_pages=source_pages[name])
            for name, paragraphs in grouped.items()
        ]
        return ExtractedPaper(paper_id=paper_id, title=title, sections=sections)

    def audit_extraction(
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
                        "reason": "No readable target sections were extracted.",
                    }
                ],
            )
        return AuditReport(complete=True, repair_required=False, issues=[])

    def audit_section(
        self,
        paper: ExtractedPaper,
        section: ExtractedSection,
        pages: list[PageArtifact],
        page_extractions: list[dict[str, Any]],
    ) -> AuditReport:
        return AuditReport(complete=True, repair_required=False, issues=[])

    def repair_extraction(
        self,
        issue: dict[str, Any],
        pages: list[PageArtifact],
        current_paper: ExtractedPaper,
    ) -> ExtractedPaper:
        return current_paper


class OpenAICompatibleVisionProvider:
    """Skeleton adapter for any compatible multimodal API."""

    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def extract_page(self, page: PageArtifact, target_sections: tuple[str, ...]) -> dict[str, Any]:
        raise NotImplementedError("Wire vendor-specific multimodal extraction here.")

    def assemble_paper(self, paper_id: str, page_extractions: list[dict[str, Any]]) -> ExtractedPaper:
        raise NotImplementedError("Local assembly is preferred; vendor assembly is optional.")

    def audit_extraction(
        self,
        paper: ExtractedPaper,
        pages: list[PageArtifact],
        page_extractions: list[dict[str, Any]],
    ) -> AuditReport:
        raise NotImplementedError("Wire vendor-specific completeness audit here.")

    def repair_extraction(
        self,
        issue: dict[str, Any],
        pages: list[PageArtifact],
        current_paper: ExtractedPaper,
    ) -> ExtractedPaper:
        raise NotImplementedError("Wire vendor-specific repair call here.")


class Seed2ProProvider:
    endpoint = "https://ark.cn-beijing.volces.com/api/v3/responses"
    model = "doubao-seed-2-0-pro-260215"

    def __init__(
        self,
        api_key: str,
        http_post: Any | None = None,
        endpoint: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key
        self.http_post = http_post or _default_http_post
        self.endpoint = endpoint or self.endpoint
        self.model = model or self.model

    def extract_page(self, page: PageArtifact, target_sections: tuple[str, ...]) -> dict[str, Any]:
        prompt = (
            "You are a research paper PDF extraction engine. Use the raw PDF text as "
            "the primary source. Use the page image only to verify layout, section "
            "boundaries, and whether text is a table, figure legend, header, footer, "
            "or body paragraph.\n"
            "Extract body text only. Target sections: " + ", ".join(target_sections) + ".\n"
            "Do not extract table text, figure legends, references, page headers, "
            "page footers, line numbers, or author affiliations unless they are part "
            "of the article title.\n"
            "Return strict JSON in this schema: "
            '{"page":1,"sections":[{"name":"Abstract","paragraphs":["complete paragraph"],'
            '"source_pages":[1]}],"excluded_content":["figure legend"]}.\n'
            f"Current page number: {page.page_number}\n"
            "Raw PDF text:\n"
            f"{page.raw_text}"
        )
        response = self._responses(
            [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": _image_data_url(page.image_path)},
            ]
        )
        return _parse_json_response(response)

    def assemble_paper(self, paper_id: str, page_extractions: list[dict[str, Any]]) -> ExtractedPaper:
        prompt = (
            "You are a research paper section assembler. Merge page-level JSON into "
            "a complete paper structure. Fix cross-page paragraph splits, abnormal "
            "spaces, and line breaks. Do not summarize, expand, or change scientific meaning. "
            "Return strict JSON in this schema: "
            '{"paper_id":"id","title":"Title","sections":[{"name":"Abstract",'
            '"paragraphs":["complete paragraph"],"source_pages":[1]}]}.\n'
            f"paper_id: {paper_id}\n"
            f"Page extraction JSON: {json.dumps(page_extractions, ensure_ascii=False)}"
        )
        data = _parse_json_response(
            self._responses([{"type": "input_text", "text": prompt}])
        )
        return _paper_from_json(paper_id, data)

    def audit_extraction(
        self,
        paper: ExtractedPaper,
        pages: list[PageArtifact],
        page_extractions: list[dict[str, Any]],
    ) -> AuditReport:
        prompt = (
            "You are a research paper extraction quality auditor. Decide whether the "
            "structured text is complete, whether body text is missing, whether figure "
            "legends/tables/references leaked in, and whether there are broken sentences, "
            "abnormal spaces, or truncated sections. Return strict JSON in this schema: "
            '{"complete":false,"repair_required":true,"issues":[{"type":"missing_paragraph",'
            '"section":"Results","pages":[5],"reason":"..."}],"notes":[]}.\n'
            f"Structured paper: {json.dumps(_paper_to_json(paper), ensure_ascii=False)}\n"
            f"Page extraction JSON: {json.dumps(page_extractions, ensure_ascii=False)}\n"
            "Raw page text: "
            f"{json.dumps([{'page': p.page_number, 'raw_text': p.raw_text} for p in pages], ensure_ascii=False)}"
        )
        content = [{"type": "input_text", "text": prompt}]
        content.extend({"type": "input_image", "image_url": _image_data_url(page.image_path)} for page in pages)
        return _audit_report_from_json(_parse_json_response(self._responses(content)))

    def audit_section(
        self,
        paper: ExtractedPaper,
        section: ExtractedSection,
        pages: list[PageArtifact],
        page_extractions: list[dict[str, Any]],
    ) -> AuditReport:
        page_numbers = {page.page_number for page in pages}
        relevant_extractions = [
            extraction
            for extraction in page_extractions
            if int(extraction.get("page", 0)) in page_numbers
        ]
        prompt = (
            "You are auditing one section of an extracted research paper. Use raw PDF "
            "text as primary evidence and the page image only for layout verification. "
            "Check whether this section is complete, readable, not contaminated by tables, "
            "figure legends, references, headers, or footers, and whether paragraphs are "
            "natural and untruncated. Return strict JSON in this schema: "
            '{"complete":true,"repair_required":false,"issues":[],"notes":["..."]}.\n'
            "Do not mark a section missing only because this article type uses nonstandard headings.\n"
            f"Paper title: {paper.title}\n"
            f"Section JSON: {json.dumps(_section_to_json(section), ensure_ascii=False)}\n"
            f"Relevant page extraction JSON: {json.dumps(relevant_extractions, ensure_ascii=False)}\n"
            "Relevant raw page text: "
            f"{json.dumps([{'page': p.page_number, 'raw_text': p.raw_text} for p in pages], ensure_ascii=False)}"
        )
        content = [{"type": "input_text", "text": prompt}]
        content.extend({"type": "input_image", "image_url": _image_data_url(page.image_path)} for page in pages)
        return _audit_report_from_json(_parse_json_response(self._responses(content)))

    def repair_extraction(
        self,
        issue: dict[str, Any],
        pages: list[PageArtifact],
        current_paper: ExtractedPaper,
    ) -> ExtractedPaper:
        issue_pages = set(issue.get("pages", []))
        relevant_pages = [page for page in pages if page.page_number in issue_pages] or pages
        prompt = (
            "You are repairing extracted research paper text. Fix only the issue reported "
            "by the auditor. Do not rewrite unrelated sections. Do not summarize or expand. "
            "Return the full repaired paper JSON in this schema: "
            '{"paper_id":"id","title":"Title","sections":[{"name":"Abstract",'
            '"paragraphs":["complete paragraph"],"source_pages":[1]}]}.\n'
            f"Audit issue: {json.dumps(issue, ensure_ascii=False)}\n"
            f"Current paper: {json.dumps(_paper_to_json(current_paper), ensure_ascii=False)}\n"
            "Relevant raw page text: "
            f"{json.dumps([{'page': p.page_number, 'raw_text': p.raw_text} for p in relevant_pages], ensure_ascii=False)}"
        )
        content = [{"type": "input_text", "text": prompt}]
        content.extend(
            {"type": "input_image", "image_url": _image_data_url(page.image_path)}
            for page in relevant_pages
        )
        data = _parse_json_response(self._responses(content))
        return _paper_from_json(current_paper.paper_id, data)

    def _responses(self, content: list[dict[str, Any]]) -> str:
        payload = {
            "model": self.model,
            "input": [{"role": "user", "content": content}],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = self.http_post(self.endpoint, headers, payload)
        return _extract_output_text(response)


def _guess_section(raw_text: str, target_sections: tuple[str, ...]) -> str:
    lowered = raw_text.casefold()
    for section in target_sections:
        if section.casefold() in lowered:
            return section
    return "Body"


def _looks_like_non_body(line: str) -> bool:
    stripped = line.strip().casefold()
    return stripped.startswith(("fig.", "figure ", "table ", "references"))


def _default_http_post(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Seed2.0 Pro API request failed: HTTP {exc.code}: {body}") from exc


def _image_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _extract_output_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    texts: list[str] = []
    for output in response.get("output", []):
        for item in output.get("content", []):
            if isinstance(item.get("text"), str):
                texts.append(item["text"])
    if texts:
        return "\n".join(texts)
    choices = response.get("choices", [])
    if choices:
        content = choices[0].get("message", {}).get("content")
        if isinstance(content, str):
            return content
    raise RuntimeError("API response did not contain output text.")


def _parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def _paper_from_json(paper_id: str, data: dict[str, Any]) -> ExtractedPaper:
    return ExtractedPaper(
        paper_id=str(data.get("paper_id") or paper_id),
        title=str(data.get("title") or paper_id),
        sections=[
            ExtractedSection(
                name=str(section.get("name", "")),
                paragraphs=[str(item) for item in section.get("paragraphs", [])],
                source_pages=[int(page) for page in section.get("source_pages", [])],
            )
            for section in data.get("sections", [])
        ],
    )


def _paper_to_json(paper: ExtractedPaper) -> dict[str, Any]:
    return {
        "paper_id": paper.paper_id,
        "title": paper.title,
        "sections": [_section_to_json(section) for section in paper.sections],
    }


def _section_to_json(section: ExtractedSection) -> dict[str, Any]:
    return {
        "name": section.name,
        "paragraphs": section.paragraphs,
        "source_pages": section.source_pages,
    }


def _audit_report_from_json(data: dict[str, Any]) -> AuditReport:
    return AuditReport(
        complete=bool(data.get("complete")),
        repair_required=bool(data.get("repair_required")),
        issues=list(data.get("issues", [])),
        notes=list(data.get("notes", [])),
    )
