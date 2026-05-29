from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path

from paper_writer_agent.library import PaperLibrary
from paper_writer_agent.models import PaperMetadata, to_jsonable
from paper_writer_agent.pdf_preprocessor import PDFPreprocessor
from paper_writer_agent.pipeline import ExtractionPipeline
from paper_writer_agent.providers import MockLLMProvider, Seed2ProProvider
from paper_writer_agent.secret_store import SecretStore


DEFAULT_WORK_DIR = Path(".paper_agent/work")
DEFAULT_LIBRARY_DIR = Path("library")
DEFAULT_SEED2_CREDENTIALS = Path(".paper_agent/secrets/seed2-pro.enc.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="paper-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="Extract, audit, repair, and store a PDF.")
    ingest.add_argument("pdf", type=Path)
    ingest.add_argument("--paper-id", required=True)
    ingest.add_argument("--keywords", required=True, help="Comma-separated keyword list.")
    ingest.add_argument("--library-dir", type=Path, default=DEFAULT_LIBRARY_DIR)
    ingest.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    ingest.add_argument("--provider", choices=["mock", "seed2-pro"], default="mock")
    ingest.add_argument("--credentials", type=Path, default=DEFAULT_SEED2_CREDENTIALS)

    search = subparsers.add_parser("search", help="Search the local paper library.")
    search.add_argument("query")
    search.add_argument("--library-dir", type=Path, default=DEFAULT_LIBRARY_DIR)

    write = subparsers.add_parser("write", help="Collect matching context for a writing request.")
    write.add_argument("request")
    write.add_argument("--library-dir", type=Path, default=DEFAULT_LIBRARY_DIR)
    write.add_argument("--limit", type=int, default=5)

    secrets = subparsers.add_parser("secrets", help="Manage encrypted API credentials.")
    secret_subparsers = secrets.add_subparsers(dest="secret_command", required=True)
    set_secret = secret_subparsers.add_parser("set-seed2-pro", help="Encrypt Seed2.0 Pro API key.")
    set_secret.add_argument("--credentials", type=Path, default=DEFAULT_SEED2_CREDENTIALS)

    args = parser.parse_args(argv)

    if args.command == "ingest":
        return _ingest(args)
    if args.command == "search":
        return _search(args)
    if args.command == "write":
        return _write(args)
    if args.command == "secrets":
        return _secrets(args)
    return 1


def _ingest(args: argparse.Namespace) -> int:
    keywords = [item.strip() for item in args.keywords.split(",") if item.strip()]
    pipeline = ExtractionPipeline(
        preprocessor=PDFPreprocessor(args.work_dir),
        llm_provider=_build_provider(args),
        work_dir=args.work_dir,
    )
    result = pipeline.extract(args.pdf, args.paper_id)
    library = PaperLibrary(args.library_dir)
    stored = library.store_paper(
        paper=result.paper,
        markdown=result.markdown,
        metadata=PaperMetadata(
            paper_id=args.paper_id,
            title=result.paper.title,
            keywords=keywords,
            source_pdf=str(args.pdf),
        ),
        quality_report=to_jsonable(result.quality_report),
    )

    extraction_dir = args.work_dir / args.paper_id
    extraction_dir.mkdir(parents=True, exist_ok=True)
    (extraction_dir / "page_extractions.json").write_text(
        json.dumps(to_jsonable(result.page_extractions), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Stored paper: {stored.paper_md}")
    print("Metadata and quality report are embedded in the Markdown front matter.")
    print(f"Quality complete: {result.quality_report.complete}")
    return 0


def _search(args: argparse.Namespace) -> int:
    results = PaperLibrary(args.library_dir).search(args.query)
    for item in results:
        print(f"{item.paper_id}\t{item.title}\t{item.paper_md}")
    return 0


def _write(args: argparse.Namespace) -> int:
    results = PaperLibrary(args.library_dir).search(args.request)[: args.limit]
    print("# Writing Request")
    print(args.request)
    print("\n# Matched Context")
    for item in results:
        print(f"\n## {item.title}")
        print(item.paper_md.read_text(encoding="utf-8")[:4000])
    return 0


def _secrets(args: argparse.Namespace) -> int:
    if args.secret_command == "set-seed2-pro":
        api_key = getpass.getpass("Seed2.0 Pro API key: ")
        pin = getpass.getpass("PIN: ")
        SecretStore(args.credentials).save_api_key(api_key=api_key, pin=pin)
        print(f"Encrypted credentials saved: {args.credentials}")
        return 0
    return 1


def _build_provider(args: argparse.Namespace):
    if args.provider == "mock":
        return MockLLMProvider()
    if args.provider == "seed2-pro":
        pin = getpass.getpass("PIN: ")
        api_key = SecretStore(args.credentials).load_api_key(pin=pin)
        return Seed2ProProvider(api_key=api_key)
    raise ValueError(f"Unsupported provider: {args.provider}")


if __name__ == "__main__":
    raise SystemExit(main())
