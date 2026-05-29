from __future__ import annotations

from pathlib import Path

from paper_writer_agent.models import PageArtifact


class PDFPreprocessor:
    def __init__(self, work_dir: Path, image_zoom: float = 1.5):
        self.work_dir = work_dir
        self.image_zoom = image_zoom

    def preprocess(self, pdf_path: Path, paper_id: str) -> list[PageArtifact]:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError(
                "PyMuPDF is required for PDF preprocessing. Install dependencies with "
                "`python -m pip install -e .`."
            ) from exc

        pdf_path = Path(pdf_path)
        output_dir = self.work_dir / paper_id / "pages"
        output_dir.mkdir(parents=True, exist_ok=True)
        artifacts: list[PageArtifact] = []

        with fitz.open(pdf_path) as document:
            matrix = fitz.Matrix(self.image_zoom, self.image_zoom)
            for index, page in enumerate(document, start=1):
                page_id = f"page_{index:03d}"
                image_path = output_dir / f"{page_id}.png"
                text_path = output_dir / f"{page_id}.txt"
                if image_path.exists() and text_path.exists():
                    raw_text = text_path.read_text(encoding="utf-8")
                else:
                    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                    pixmap.save(image_path)
                    raw_text = page.get_text("text")
                    text_path.write_text(raw_text, encoding="utf-8")
                artifacts.append(
                    PageArtifact(
                        page_number=index,
                        image_path=image_path,
                        text_path=text_path,
                        raw_text=raw_text,
                    )
                )

        return artifacts
