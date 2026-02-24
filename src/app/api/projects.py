from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Any

from src.app.domain.models import (
    CreateProjectRequest,
    Project,
    ProjectHistoryEntry,
    Revision,
    SourceFile,
    SourceFormat,
)
from src.app.storage import file_repo
from src.app.ingestion.pipeline import run_ingestion

router = APIRouter()


def _detect_format(filename: str) -> SourceFormat:
    lower = filename.lower()
    if lower.endswith(".ifc"):
        return SourceFormat.IFC
    if lower.endswith(".pdf"):
        return SourceFormat.PDF
    if lower.endswith(".dwg"):
        return SourceFormat.DWG
    raise HTTPException(status_code=400, detail=f"Unsupported file format: {filename}")


@router.post("", response_model=Project)
async def create_project(req: CreateProjectRequest):
    project = Project(name=req.name, description=req.description)
    file_repo.save_project(project)
    return project


@router.get("", response_model=list[Project])
async def list_projects():
    return file_repo.list_projects()


@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: str):
    proj = file_repo.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@router.post("/{project_id}/revisions", response_model=Revision)
async def create_revision(
    project_id: str,
    files: list[UploadFile] = File(...),
    metadata: str = Form("{}"),
):
    proj = file_repo.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    import json
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError:
        meta = {}

    revision = Revision(project_id=project_id, metadata=meta)
    sources: list[SourceFile] = []

    for upload in files:
        fmt = _detect_format(upload.filename or "unknown")
        content = await upload.read()
        source_hash, stored_path = file_repo.store_source_file(project_id, upload.filename or "unknown", content)
        sources.append(
            SourceFile(
                file_name=upload.filename or "unknown",
                source_format=fmt,
                source_hash=source_hash,
                size_bytes=len(content),
                stored_path=stored_path,
            )
        )

    revision.sources = sources
    file_repo.save_revision(revision)

    await run_ingestion(project_id, revision)

    return revision


@router.get("/{project_id}/revisions", response_model=list[Revision])
async def list_revisions(project_id: str):
    return file_repo.list_revisions(project_id)


@router.get("/{project_id}/history", response_model=list[ProjectHistoryEntry])
async def project_history(project_id: str):
    proj = file_repo.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    revisions = file_repo.list_revisions(project_id)
    validations = file_repo.list_validations_for_project(project_id)

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
