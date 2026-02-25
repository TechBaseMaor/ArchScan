"""Review queue API — list, filter, approve/reject pending manual-review items."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from src.app.domain.models import (
    ReviewDecisionRequest,
    ReviewItem,
    ReviewStatus,
)
from src.app.storage import repo
from src.app.i18n import resolve_locale, t

router = APIRouter()


@router.get("", response_model=list[ReviewItem])
async def list_reviews(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    review_type: Optional[str] = None,
):
    """List review items, optionally filtered by project, status, or type."""
    items = repo.list_review_items(project_id=project_id, status=status)
    if review_type:
        items = [i for i in items if i.review_type == review_type]
    return items


@router.get("/{review_id}", response_model=ReviewItem)
async def get_review(review_id: str, request: Request):
    locale = resolve_locale(request)
    item = repo.get_review_item(review_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    return item


@router.post("/{review_id}/decide", response_model=ReviewItem)
async def decide_review(review_id: str, req: ReviewDecisionRequest, request: Request):
    """Approve or reject a pending review item."""
    locale = resolve_locale(request)
    item = repo.get_review_item(review_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")

    if item.status not in (ReviewStatus.PENDING_REVIEW,):
        raise HTTPException(
            status_code=400,
            detail=f"Review item already resolved (status={item.status.value})",
        )

    if req.decision == "approved":
        item.status = ReviewStatus.APPROVED
    elif req.decision == "rejected":
        item.status = ReviewStatus.REJECTED
    else:
        raise HTTPException(status_code=400, detail="Decision must be 'approved' or 'rejected'")

    item.reviewer = req.reviewer
    item.decision_notes = req.notes
    item.resolved_at = datetime.utcnow()

    repo.save_review_item(item)
    repo.log_audit_event(
        "review_decided",
        "review",
        review_id,
        {
            "decision": req.decision,
            "reviewer": req.reviewer,
            "project_id": item.project_id,
            "file_name": item.file_name,
        },
    )
    return item


@router.get("/summary/counts")
async def review_summary(project_id: Optional[str] = None):
    """Quick count of pending vs resolved review items."""
    items = repo.list_review_items(project_id=project_id)
    pending = sum(1 for i in items if i.status == ReviewStatus.PENDING_REVIEW)
    approved = sum(1 for i in items if i.status == ReviewStatus.APPROVED)
    rejected = sum(1 for i in items if i.status == ReviewStatus.REJECTED)
    return {
        "total": len(items),
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
    }
