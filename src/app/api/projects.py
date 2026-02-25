from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from typing import Any

from src.app.domain.models import (
    CreateProjectRequest,
    DocumentRole,
    ExtractedFact,
    Project,
    ProjectHistoryEntry,
    Revision,
    RevisionSummary,
    SourceFile,
    SourceFormat,
)
from src.app.storage import repo
from src.app.ingestion.pipeline import run_ingestion
from src.app.ingestion.bundle_classifier import classify_source
from src.app.i18n import resolve_locale, t

router = APIRouter()


def _detect_format(filename: str, locale: str = "en") -> SourceFormat:
    lower = filename.lower()
    if lower.endswith(".ifc"):
        return SourceFormat.IFC
    if lower.endswith(".pdf"):
        return SourceFormat.PDF
    if lower.endswith(".dwg"):
        return SourceFormat.DWG
    if lower.endswith(".dwfx"):
        return SourceFormat.DWFX
    raise HTTPException(status_code=400, detail=t("error.unsupported_format", locale, filename=filename))


@router.post("", response_model=Project)
async def create_project(req: CreateProjectRequest):
    project = Project(name=req.name, description=req.description)
    repo.save_project(project)
    return project


@router.get("", response_model=list[Project])
async def list_projects():
    return repo.list_projects()


@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: str, request: Request):
    locale = resolve_locale(request)
    proj = repo.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=t("error.project_not_found", locale))
    return proj


@router.post("/{project_id}/revisions", response_model=Revision)
async def create_revision(
    project_id: str,
    request: Request,
    files: list[UploadFile] = File(...),
    metadata: str = Form("{}"),
):
    locale = resolve_locale(request)
    proj = repo.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=t("error.project_not_found", locale))

    import json
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError:
        meta = {}

    revision = Revision(project_id=project_id, metadata=meta)
    sources: list[SourceFile] = []

    for upload in files:
        fmt = _detect_format(upload.filename or "unknown", locale)
        content = await upload.read()
        source_hash, stored_path = repo.store_source_file(project_id, upload.filename or "unknown", content)
        sf = SourceFile(
            file_name=upload.filename or "unknown",
            source_format=fmt,
            source_hash=source_hash,
            size_bytes=len(content),
            stored_path=stored_path,
        )
        role, doc_type = classify_source(sf)
        sf.document_role = role
        sf.document_type = doc_type
        sources.append(sf)

    revision.sources = sources
    repo.save_revision(revision)

    await run_ingestion(project_id, revision)

    return revision


@router.get("/{project_id}/revisions", response_model=list[Revision])
async def list_revisions(project_id: str):
    return repo.list_revisions(project_id)


@router.get("/{project_id}/revisions/{revision_id}/facts", response_model=list[ExtractedFact])
async def get_revision_facts(project_id: str, revision_id: str, request: Request):
    locale = resolve_locale(request)
    proj = repo.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=t("error.project_not_found", locale))
    rev = repo.get_revision(project_id, revision_id)
    if not rev:
        raise HTTPException(status_code=404, detail="Revision not found")
    return repo.load_facts(project_id, revision_id)


@router.get("/{project_id}/revisions/{revision_id}/summary", response_model=RevisionSummary)
async def get_revision_summary(project_id: str, revision_id: str, request: Request):
    locale = resolve_locale(request)
    proj = repo.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=t("error.project_not_found", locale))
    rev = repo.get_revision(project_id, revision_id)
    if not rev:
        raise HTTPException(status_code=404, detail="Revision not found")

    from src.app.reporting.insights_service import build_revision_summary
    facts = repo.load_facts(project_id, revision_id)
    return build_revision_summary(project_id, revision_id, facts)


@router.get("/{project_id}/history", response_model=list[ProjectHistoryEntry])
async def project_history(project_id: str, request: Request):
    locale = resolve_locale(request)
    proj = repo.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=t("error.project_not_found", locale))

    revisions = repo.list_revisions(project_id)
    validations = repo.list_validations_for_project(project_id)

    entries = []
    for rev in revisions:
        val_count = sum(1 for v in validations if v.revision_id == rev.revision_id)
        entries.append(
            ProjectHistoryEntry(
                revision_id=rev.revision_id,
                created_at=rev.created_at,
                source_count=len(rev.sources),
                validation_count=val_count,
            )
        )
    return entries
