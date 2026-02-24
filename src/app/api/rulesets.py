from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request

from src.app.domain.models import RuleSet
from src.app.storage import repo
from src.app.i18n import resolve_locale, t

router = APIRouter()


@router.post("", response_model=RuleSet)
async def create_ruleset(ruleset: RuleSet):
    repo.save_ruleset(ruleset)
    return ruleset


@router.get("", response_model=List[RuleSet])
async def list_rulesets():
    return repo.list_rulesets()


@router.get("/{ruleset_id}", response_model=RuleSet)
async def get_ruleset(ruleset_id: str, request: Request, version: Optional[str] = None):
    locale = resolve_locale(request)
    rs = repo.get_ruleset(ruleset_id, version)
    if not rs:
        raise HTTPException(status_code=404, detail=t("error.ruleset_not_found", locale))
    return rs
