from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.app.domain.models import (
    Finding,
    StartValidationRequest,
    ValidationRun,
)
from src.app.storage import file_repo
from src.app.validation.worker import validation_manager

router = APIRouter()


@router.post("", response_model=ValidationRun)
async def start_validation(req: StartValidationRequest):
    proj = file_repo.get_project(req.project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    rev = file_repo.get_revision(req.project_id, req.revision_id)
    if not rev:
        raise HTTPException(status_code=404, detail="Revision not found")

    ruleset = file_repo.get_ruleset(req.ruleset_id)
    if not ruleset:
        raise HTTPException(status_code=404, detail="RuleSet not found")

    run = ValidationRun(
        project_id=req.project_id,
        revision_id=req.revision_id,
        ruleset_id=req.ruleset_id,
    )
    file_repo.save_validation(run)
    file_repo.log_audit_event("create", "validation", run.validation_id)

    await validation_manager.enqueue(run.validation_id)

    return run


@router.get("/{validation_id}", response_model=ValidationRun)
async def get_validation(validation_id: str):
    run = file_repo.get_validation(validation_id)
    if not run:
        raise HTTPException(status_code=404, detail="Validation not found")
    return run


@router.get("/{validation_id}/findings", response_model=list[Finding])
async def get_findings(validation_id: str):
    run = file_repo.get_validation(validation_id)
    if not run:
        raise HTTPException(status_code=404, detail="Validation not found")
    return file_repo.load_findings(validation_id)


@router.get("/{validation_id}/report")
async def get_report(validation_id: str):
    run = file_repo.get_validation(validation_id)
    if not run:
        raise HTTPException(status_code=404, detail="Validation not found")
    pdf_path = file_repo.report_path(validation_id)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Report not yet generated")
    return FileResponse(str(pdf_path), media_type="application/pdf", filename=f"report_{validation_id}.pdf")
