from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from src.app.domain.models import (
    Finding,
    StartValidationRequest,
    ValidationRun,
)
from src.app.storage import repo
from src.app.validation.worker import validation_manager
from src.app.i18n import resolve_locale, t

router = APIRouter()


@router.post("", response_model=ValidationRun)
async def start_validation(req: StartValidationRequest, request: Request):
    locale = resolve_locale(request)
    proj = repo.get_project(req.project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=t("error.project_not_found", locale))

    rev = repo.get_revision(req.project_id, req.revision_id)
    if not rev:
        raise HTTPException(status_code=404, detail=t("error.revision_not_found", locale))

    ruleset = repo.get_ruleset(req.ruleset_id)
    if not ruleset:
        raise HTTPException(status_code=404, detail=t("error.ruleset_not_found", locale))

    run = ValidationRun(
        project_id=req.project_id,
        revision_id=req.revision_id,
        ruleset_id=req.ruleset_id,
    )
    repo.save_validation(run)
    repo.log_audit_event("create", "validation", run.validation_id)

    await validation_manager.enqueue(run.validation_id)

    return run


@router.get("/{validation_id}", response_model=ValidationRun)
async def get_validation(validation_id: str, request: Request):
    locale = resolve_locale(request)
    run = repo.get_validation(validation_id)
    if not run:
        raise HTTPException(status_code=404, detail=t("error.validation_not_found", locale))
    return run


@router.get("/{validation_id}/findings", response_model=list[Finding])
async def get_findings(validation_id: str, request: Request):
    locale = resolve_locale(request)
    run = repo.get_validation(validation_id)
    if not run:
        raise HTTPException(status_code=404, detail=t("error.validation_not_found", locale))
    return repo.load_findings(validation_id)


@router.get("/{validation_id}/report")
async def get_report(validation_id: str, request: Request):
    locale = resolve_locale(request)
    run = repo.get_validation(validation_id)
    if not run:
        raise HTTPException(status_code=404, detail=t("error.validation_not_found", locale))
    pdf_path = repo.report_path(validation_id)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=t("error.report_not_generated", locale))
    return FileResponse(str(pdf_path), media_type="application/pdf", filename=f"report_{validation_id}.pdf")
