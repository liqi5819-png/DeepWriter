# Paper Writing Agent Design

## Objective

Build a local-first research paper writing agent that extracts clean Markdown from PDF papers, audits extraction completeness with an LLM, repairs omissions, stores papers by keyword, and prepares retrieved paper context for later LLM-based academic writing.

## Model Strategy

Seed2.0 Pro is the primary model for multimodal extraction, completeness auditing, and repair. KIMI-K2.5 is reserved for secondary auditing, batch checking, and optional writing generation once output style is evaluated.

The current implementation keeps model APIs behind a provider interface. Seed2.0 Pro is implemented through the Volcengine Ark responses API. KIMI-K2.5 remains a future provider.

API keys are stored only in encrypted local credential files. The encryption key is derived from a user-entered PIN with PBKDF2-HMAC-SHA256, and the credential payload is encrypted with Fernet authenticated encryption. The API key and PIN are not written to source files or documentation.

## Components

### PDF Preprocessor

The PDF preprocessor uses PyMuPDF to render each PDF page to a downsampled image and extract raw page text. Raw text is the primary evidence for extraction. Page images are used to verify layout, identify figure/table regions, and catch exclusions that text extraction alone cannot distinguish.

Preprocessing is cached. Existing page images and text files are reused on later runs.

### LLM Provider

The LLM provider has four responsibilities:

- Extract target paper sections from each page.
- Audit each assembled section against relevant source pages.
- Repair concrete audit issues.

The provider interface is model-agnostic so Seed2.0 Pro and KIMI-K2.5 can be added without changing the pipeline.

`Seed2ProProvider` sends raw page text first and relevant page images as layout verification evidence to the Ark responses endpoint. The CLI decrypts the API key at runtime after asking for a PIN.

### Local Section Assembler

The local assembler consumes page-level LLM extraction JSON and merges it into `ExtractedPaper`. It handles title extraction, section grouping, paragraph cleanup, and simple cross-page paragraph joins. This avoids a large whole-paper LLM assembly call.

### Extraction Pipeline

The pipeline preprocesses the PDF, calls page extraction, assembles the paper locally, builds Markdown, audits completeness per section, and performs bounded repair loops. Repair operates on concrete audit issues instead of rerunning the whole PDF by default.

The default repair loop count is one. Intermediate artifacts are cached under `.paper_agent/work/<paper_id>/`, including page extractions, assembled paper JSON, repair JSON, quality report, and final Markdown.

### Paper Library

The library stores one Markdown file per paper directly under `library/`. Keywords, source PDF, and the quality report summary are embedded in Markdown front matter. Keyword search scans front matter and body text; embedding retrieval can be added later.

### Writing Context Collector

The first writing command retrieves matching papers and prints context. Later it will call the writer model with the writing request, retrieved paper sections, and style constraints.

## Data Flow

```text
PDF -> page images/text -> page extraction JSON -> local assembly -> Markdown
    -> per-section completeness audit -> one repair round -> keyword library -> writing context
```

## Error Handling

PDF preprocessing raises a clear error if PyMuPDF is missing. Extraction repair is bounded by `max_repair_rounds` to avoid infinite loops. Library storage requires at least one keyword.

## Testing

Tests cover Markdown cleaning, keyword storage/search, and repair-loop orchestration with a fake provider. API-specific tests should be added when real Seed2.0 Pro and KIMI-K2.5 adapters are implemented.
