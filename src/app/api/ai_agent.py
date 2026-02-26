"""AI Agent API — endpoints for enrichment, proposal management, learning events, and KPI evaluation."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException

from src.app.config import settings
from src.app.domain.models import (
    AiEnrichmentRequest,
    AiProposal,
    AiProposalDecisionRequest,
    LearnedMapping,
    LearningEvent,
    ProposalStatus,
)
from src.app.storage import repo
from src.app.ai.agent_service import create_learning_event_from_decision, run_enrichment
from src.app.pilot.kpi_gates import KpiReport, evaluate_kpis

logger = logging.getLogger(__name__)
router = APIRouter()

MIN_ACCEPTANCE_FOR_PROMOTION = 3
MIN_CONFIDENCE_FOR_PROMOTION = 0.7


@router.get("/status")
async def ai_status():
    """Check whether the AI agent is available."""
    return {
        "enabled": settings.llm.enabled,
        "available": settings.llm_available,
        "provider": settings.llm.provider if settings.llm.enabled else None,
        "model": settings.llm.model if settings.llm.enabled else None,
    }


@router.post("/enrich", response_model=list[AiProposal])
async def enrich(request: AiEnrichmentRequest):
    """Run AI enrichment on a project revision and return proposals."""
    revision = repo.get_revision(request.project_id, request.revision_id)
    if not revision:
        raise HTTPException(404, "Revision not found")

    facts = repo.load_facts(request.project_id, request.revision_id)
    learned = repo.list_learned_mappings(promoted_only=False)

    try:
        proposals = await run_enrichment(
            project_id=request.project_id,
            revision_id=request.revision_id,
            facts=facts,
            sources=revision.sources,
            learned_mappings=learned,
            scope=request.scope,
        )
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))

    repo.save_proposals(proposals)
    repo.log_audit_event(
        "ai_enrichment",
        "revision",
        request.revision_id,
        {"project_id": request.project_id, "proposals_count": len(proposals)},
    )

    return proposals


@router.get("/proposals/{project_id}/{revision_id}", response_model=list[AiProposal])
async def list_revision_proposals(
    project_id: str,
    revision_id: str,
    status: Optional[str] = None,
):
    """List AI proposals for a revision, optionally filtered by status."""
    return repo.list_proposals(project_id, revision_id, status)


@router.post("/proposals/{project_id}/{revision_id}/{proposal_id}/decide", response_model=AiProposal)
async def decide_proposal(
    project_id: str,
    revision_id: str,
    proposal_id: str,
    request: AiProposalDecisionRequest,
):
    """Accept, reject, or edit an AI proposal."""
    proposal = repo.get_proposal(project_id, revision_id, proposal_id)
    if not proposal:
        raise HTTPException(404, "Proposal not found")

    status_map = {
        "accepted": ProposalStatus.ACCEPTED,
        "rejected": ProposalStatus.REJECTED,
        "edited": ProposalStatus.EDITED,
    }
    new_status = status_map.get(request.decision)
    if not new_status:
        raise HTTPException(400, f"Invalid decision: {request.decision}")

    proposal.status = new_status
    proposal.decided_by = request.user
    proposal.decided_at = datetime.utcnow()
    if request.edited_value is not None:
        proposal.edited_value = request.edited_value
    if request.edited_label:
        proposal.edited_label = request.edited_label

    repo.save_proposal(proposal)

    learning_event = create_learning_event_from_decision(
        proposal=proposal,
        decision=request.decision,
        user=request.user,
        edited_value=request.edited_value,
        edited_label=request.edited_label,
    )
    repo.save_learning_event(learning_event)

    _maybe_promote_mapping(learning_event)

    repo.log_audit_event(
        "ai_proposal_decision",
        "proposal",
        proposal_id,
        {
            "decision": request.decision,
            "user": request.user,
            "project_id": project_id,
        },
    )

    return proposal


@router.get("/learning/events", response_model=list[LearningEvent])
async def list_events(
    event_type: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
):
    """List learning events (most recent first)."""
    return repo.list_learning_events(event_type, category, limit)


@router.get("/learning/mappings", response_model=list[LearnedMapping])
async def list_mappings(promoted_only: bool = False):
    """List learned mappings."""
    return repo.list_learned_mappings(promoted_only)


def _maybe_promote_mapping(event: LearningEvent) -> None:
    """Check if a correction pattern should be promoted to a learned mapping."""
    if event.event_type.value not in ("proposal_accepted", "proposal_edited"):
        return
    if not event.original_label or not event.canonical_label:
        return

    existing = repo.list_learned_mappings(promoted_only=False)
    match = None
    for m in existing:
        if m.source_pattern == event.original_label and m.canonical_term == event.canonical_label:
            match = m
            break

    if match:
        match.acceptance_count += 1
        match.updated_at = datetime.utcnow()
        if (
            match.acceptance_count >= MIN_ACCEPTANCE_FOR_PROMOTION
            and not match.promoted
        ):
            match.confidence = min(1.0, match.acceptance_count * 0.15)
            if match.confidence >= MIN_CONFIDENCE_FOR_PROMOTION:
                match.promoted = True
                match.version += 1
                logger.info("Promoted mapping: '%s' → '%s'", match.source_pattern, match.canonical_term)
        repo.save_learned_mapping(match)
    else:
        new_mapping = LearnedMapping(
            source_pattern=event.original_label,
            canonical_term=event.canonical_label,
            category=event.category,
            unit=event.unit,
            acceptance_count=1,
            jurisdiction=event.jurisdiction,
            document_type=event.document_type,
        )
        repo.save_learned_mapping(new_mapping)


@router.get("/kpi/{project_id}/{revision_id}", response_model=KpiReport)
async def evaluate_revision_kpis(project_id: str, revision_id: str):
    """Evaluate KPI gates for a project revision (baseline vs enriched)."""
    facts = repo.load_facts(project_id, revision_id)
    proposals = repo.list_proposals(project_id, revision_id)

    accepted_proposals = [p for p in proposals if p.status in (ProposalStatus.ACCEPTED, ProposalStatus.EDITED)]
    from src.app.domain.models import ExtractedFact, FactType
    enriched_facts = list(facts)
    for p in accepted_proposals:
        enriched_facts.append(ExtractedFact(
            revision_id=revision_id,
            source_hash="ai-enriched",
            fact_type=FactType.TEXTUAL,
            category=p.category,
            label=p.edited_label or p.label,
            value=p.edited_value if p.edited_value is not None else p.value,
            unit=p.unit,
            confidence=p.confidence,
            extraction_method="ai_agent",
        ))

    return evaluate_kpis(
        baseline_facts=facts,
        enriched_facts=enriched_facts,
        proposals=proposals,
    )
