"""Demo endpoints — bootstrap sample project and list available sample files."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.app.config import settings
from src.app.domain.models import Project, Revision, SourceFile, SourceFormat
from src.app.storage import repo
from src.app.ingestion.pipeline import run_ingestion

logger = logging.getLogger(__name__)

router = APIRouter()

_DEMO_PDF_CONTENT = """\
תוכנית בניין למגורים – מגדל תל אביב

שטח ברוטו: 185 m2
שטח נטו: 152 m2
שטח שירות: 33 m2

גובה מבנה: 12.5 m
גובה תקרה: 2.8 m
גובה קומה: 3.1 m

קומה 1 – מפלס כניסה
קומה 2 – קומת מגורים
קומה 3 – קומת מגורים
קומה 4 – גג

חלונות: 1.2x1.5 m
דלתות: 0.9x2.1 m
חלונות: 8 יח'
דלתות: 5 יח'

קו בניין קדמי: 4.0 m
קו בניין אחורי: 3.0 m
קו בניין צדדי: 2.5 m

סעיף 4.1.2 – גובה מקסימלי
סעיף 5.3 – קווי בניין
"""


class SampleFileInfo(BaseModel):
    name: str
    description: str
    format: str
    size_hint: str
    download_url: str


@router.post("/bootstrap", response_model=Project)
async def bootstrap_demo():
    """Create a demo project with a synthetic PDF, run ingestion, return the project."""
    project = Project(name="פרויקט דמו – מגדל תל אביב", description="פרויקט דוגמה עם נתוני מבנה לדוגמה")
    repo.save_project(project)

    file_name = "demo_building_plan.pdf"
    pdf_bytes = _build_demo_pdf()
    source_hash, stored_path = repo.store_source_file(project.project_id, file_name, pdf_bytes)

    revision = Revision(
        project_id=project.project_id,
        sources=[
            SourceFile(
                file_name=file_name,
                source_format=SourceFormat.PDF,
                source_hash=source_hash,
                size_bytes=len(pdf_bytes),
                stored_path=stored_path,
            )
        ],
    )
    repo.save_revision(revision)

    await run_ingestion(project.project_id, revision)

    logger.info("Demo project created: %s (revision %s)", project.project_id, revision.revision_id)
    return project


@router.get("/samples", response_model=list[SampleFileInfo])
async def list_sample_files():
    """Return metadata for downloadable sample files."""
    samples: list[SampleFileInfo] = [
        SampleFileInfo(
            name="demo_building_plan.pdf",
            description="תוכנית בניין סינתטית עם שטחים, גבהים, פתחים וקווי בניין",
            format="pdf",
            size_hint="~2 KB",
            download_url="/demo/samples/download/demo_building_plan.pdf",
        ),
    ]

    synth_dir = settings.golden_dataset_dir / "simple"
    if synth_dir.exists():
        for pdf_path in sorted(synth_dir.glob("*.pdf")):
            samples.append(
                SampleFileInfo(
                    name=pdf_path.name,
                    description=f"קובץ דוגמה מהמאגר: {pdf_path.stem}",
                    format="pdf",
                    size_hint=f"~{pdf_path.stat().st_size // 1024 or 1} KB",
                    download_url=f"/demo/samples/download/{pdf_path.name}",
                )
            )

    return samples


@router.get("/samples/download/{filename}")
async def download_sample(filename: str):
    """Serve a sample file for manual download."""
    if filename == "demo_building_plan.pdf":
        pdf_bytes = _build_demo_pdf()
        tmp = settings.upload_dir / "demo_building_plan.pdf"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(pdf_bytes)
        return FileResponse(str(tmp), filename=filename, media_type="application/pdf")

    safe_name = Path(filename).name
    candidate = settings.golden_dataset_dir / "simple" / safe_name
    if candidate.exists() and candidate.suffix in (".pdf", ".ifc"):
        return FileResponse(str(candidate), filename=safe_name)

    raise HTTPException(status_code=404, detail="Sample file not found")


def _build_demo_pdf() -> bytes:
    """Generate a PDF from the demo text content.

    fpdf2 built-in fonts don't support Hebrew glyphs, so we produce
    a minimal valid PDF directly when fpdf encoding fails, or fall back
    to raw UTF-8 bytes (which the raw-text extraction path handles).
    """
    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "", 12)
        for line in _DEMO_PDF_CONTENT.strip().split("\n"):
            pdf.cell(0, 8, line.strip(), new_x="LMARGIN", new_y="NEXT")
        return pdf.output()
    except Exception:
        return _DEMO_PDF_CONTENT.encode("utf-8")
