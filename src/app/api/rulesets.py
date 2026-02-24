from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException

from src.app.domain.models import RuleSet
from src.app.storage import file_repo

router = APIRouter()


@router.post("", response_model=RuleSet)
async def create_ruleset(ruleset: RuleSet):
    file_repo.save_ruleset(ruleset)
    return ruleset


@router.get("", response_model=List[RuleSet])
async def list_rulesets():
    return file_repo.list_rulesets()


@router.get("/{ruleset_id}", response_model=RuleSet)
async def get_ruleset(ruleset_id: str, version: Optional[str] = None):
    rs = file_repo.get_ruleset(ruleset_id, version)
    if not rs:
        raise HTTPException(status_code=404, detail="RuleSet not found")
    return rs
