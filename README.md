# LLM Research Paper Writing Agent

This project is a local-first scaffold for building an LLM-based research paper writing agent. It is designed around one core principle: PDF parsing, extraction quality review, and repair should be driven by a multimodal LLM, while local tools handle deterministic preprocessing, storage, and retrieval.

The current implementation provides the full pipeline shape with a local mock LLM provider. Seed2.0 Pro and KIMI-K2.5 can be wired later inside the provider layer without changing the rest of the system.

## Goals

- Extract readable, complete paper text from PDFs into Markdown.
- Keep only the target paper sections:
  - Title
  - Abstract
  - Introduction
  - Materials and Methods
  - Results
  - Discussion
- Exclude tables, figure legends, references, page headers, footers, and other non-body text.
- Use an LLM to judge whether extraction is complete and repair missing or corrupted sections.
- Store extracted papers by keyword for later writing.
- Retrieve relevant paper text and prepare writing context for LLM-based academic drafting.

## Recommended Model Strategy

Use Seed2.0 Pro as the default model for the main pipeline:

- `extractor`: Seed2.0 Pro
- `auditor`: Seed2.0 Pro
- `repairer`: Seed2.0 Pro
- `secondary_auditor`: KIMI-K2.5
- `writer`: configurable after writing-style tests

KIMI-K2.5 is useful as a second auditor, lower-cost batch reviewer, or alternate writer when its output style fits the target field better.

## Architecture

```text
PDF
  |
  v
PDFPreprocessor
  - renders each page to downsampled PNG
  - extracts raw page text as auxiliary evidence
  - reuses cached page images and text when present
  |
  v
LLM Page Extractor
  - uses raw PDF text as primary evidence
  - uses page image only to verify layout and exclusions
  - extracts only target body sections
  |
  v
Local Section Assembler
  - merges page-level output
  - repairs broken paragraphs and cross-page splits
  - produces structured paper data
  |
  v
Markdown Builder
  - writes clean, LLM-readable Markdown
  |
  v
LLM Completeness Auditor
  - audits per section using relevant pages only
  - checks omissions, section truncation, contamination, bad spacing
  |
  v
Repair Loop
  - reprocesses issue pages or sections
  - defaults to one repair round
  |
  v
Paper Library
  - stores one Markdown file per paper
  - embeds keywords, metadata, and quality report in front matter
  |
  v
Writing Context Collector
  - retrieves matching papers for later LLM generation
```

## Project Layout

```text
paper_writer_agent/
  cli.py                Command-line interface
  library.py            Keyword-based paper storage and search
  markdown_builder.py   Clean Markdown generation
  assembler.py          Local section assembly from page extraction JSON
  models.py             Shared dataclasses
  pdf_preprocessor.py   PDF page rendering and raw text extraction
  pipeline.py           Extraction, audit, and repair orchestration
  providers.py          Mock provider and future API adapter location
tests/
  test_library.py
  test_markdown_builder.py
  test_pipeline.py
```

Runtime output:

```text
.paper_agent/
  work/
    paper_id/
      pages/
      page_001.png
      page_001.txt
      page_extractions.json
      assembled_paper.json
      assembled_paper.repair_1.json
      quality_report.json
      paper.final.md
library/
  paper_id.md
```

## Setup

```bash
python -m pip install -e .[dev]
```

`PyMuPDF` is used for local PDF preprocessing.

## Commands

### Save Seed2.0 Pro Credentials

Run this once and enter the API key and PIN when prompted:

```bash
paper-agent secrets set-seed2-pro
```

The API key is not shown on screen and is not saved as plaintext.

### Ingest A PDF

```bash
paper-agent ingest path/to/paper.pdf --paper-id paper-001 --keywords immunology,tumor
```

Use the real Seed2.0 Pro provider:

```bash
paper-agent ingest path/to/paper.pdf --paper-id paper-001 --keywords immunology,tumor --provider seed2-pro
```

The command asks for the PIN before making API calls.

This runs:

1. PDF page preprocessing.
2. Page-level extraction.
3. Local section assembly.
4. Per-section completeness audit.
5. One repair loop by default if needed.
6. Markdown and metadata storage.

By default, the CLI uses `MockLLMProvider`, so it can validate the local pipeline without API calls. Use `--provider seed2-pro` to call Seed2.0 Pro through Volcengine Ark responses API.

### Search The Library

```bash
paper-agent search "tumor immune microenvironment"
```

### Collect Writing Context

```bash
paper-agent write "Write an Introduction paragraph about tumor immune microenvironment and immunotherapy response"
```

This currently prints matched context. After the writing model is wired, this command can call the writer LLM with retrieved paper text and your writing request.

## LLM Provider Integration

The provider interface is defined by `ExtractionPipeline`:

```python
extract_page(page, target_sections)
assemble_paper(paper_id, page_extractions)
audit_extraction(paper, pages, page_extractions)
repair_extraction(issue, pages, current_paper)
```

Seed2.0 Pro is implemented in `paper_writer_agent/providers.py` as `Seed2ProProvider`. It calls:

```text
https://ark.cn-beijing.volces.com/api/v3/responses
```

with model:

```text
doubao-seed-2-0-pro-260215
```

KIMI-K2.5 can be added as a second provider using the same interface. Keep vendor-specific request bodies inside provider classes only.

Expected extraction behavior:

- Use raw PDF text as the primary source.
- Use page image only to verify layout and exclude non-body content.
- Do not summarize the paper.
- Do not rewrite scientific meaning.
- Remove broken line wrapping and abnormal spacing.
- Exclude figure legends, table text, references, headers, and footers.
- Preserve full natural paragraphs.

Expected audit behavior:

- Audit one section at a time using only relevant pages.
- Report whether extraction is complete.
- Identify missing pages, sections, or paragraphs.
- Detect contamination from figure legends, tables, and references.
- Detect unnatural spacing, broken sentences, and section truncation.
- Return concrete repair targets by page and section.

## Development

Run tests:

```bash
python -m pytest -q
```

The current tests cover:

- Markdown cleanup and section formatting.
- Keyword-based library storage and search.
- Flat library storage with one Markdown file per paper.
- Audit-triggered repair loop behavior.

## Current Status

Implemented:

- Local Python package.
- CLI scaffold.
- PDF preprocessing with PyMuPDF.
- Downsampled page images by default.
- Cached page preprocessing, page extraction, assembly, audit, repair, and final Markdown artifacts.
- LLM provider abstraction.
- Mock LLM provider.
- Seed2.0 Pro provider for Volcengine Ark responses API.
- PIN-protected encrypted API credential storage.
- LLM page extraction, local assembly, per-section audit, and one-round repair pipeline.
- Markdown output.
- Keyword-based library storage and search.
- README and tests.

Not yet implemented:

- Actual KIMI-K2.5 API calls.
- Embedding-based semantic retrieval.
- Final writer LLM generation.
