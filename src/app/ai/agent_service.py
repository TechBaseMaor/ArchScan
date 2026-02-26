"""AI Agent orchestration service — enriches findings via structured LLM calls.

Builds context from extracted facts, calls the configured LLM provider,
and returns deterministic JSON proposals. All proposals require human
confirmation before becoming accepted findings.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from src.app.config import settings
from src.app.domain.models import (
    AiProposal,
    ExtractedFact,
    LearningEvent,
    LearningEventType,
    LearnedMapping,
    ProposalStatus,
    SourceFile,
)

logger = logging.getLogger(__name__)

_ENRICHMENT_SYSTEM_PROMPT = """\
You are an expert Israeli architectural permit analyst. You review extracted data
from building permit documents (submission plans, statutory plans, spatial guidelines,
area calculations, site surveys, and policy documents).

Your task: given the already-extracted facts and document metadata, identify
additional facts/parameters that should have been extracted but were missed.

Rules:
1. Only propose facts you can justify from the provided document text/context.
2. Each proposal must include: category, label, value, unit, confidence (0-1), and reasoning.
3. Use Hebrew labels when the source text is in Hebrew.
4. Categories must be one of: area, height, setback, parking, dwelling_units, coverage,
   level, floor_summary, regulatory_threshold, text_clause, environment, survey.
5. Return ONLY valid JSON array of proposals. No markdown fences.
"""

_ENRICHMENT_USER_TEMPLATE = """\
Project context:
- Document types present: {doc_types}
- Total facts already extracted: {total_facts}
- Categories covered: {categories}
- Categories missing or sparse: {missing}

Existing facts summary:
{facts_summary}

Learned mappings (from previous corrections):
{learned_mappings}

Based on typical Israeli permit requirements, propose additional findings that
are likely present but were not extracted. Focus on the missing/sparse categories.

Return a JSON array where each element has:
{{"category": "...", "label": "...", "value": ..., "unit": "...", "confidence": 0.0-1.0, "reasoning": "...", "source_document": "..."}}
"""


def _build_facts_summary(facts: list[ExtractedFact], max_items: int = 50) -> str:
    """Summarize existing facts for the LLM context window."""
    by_cat: dict[str, list[str]] = {}
    for f in facts:
        by_cat.setdefault(f.category, []).append(
            f"{f.label}: {f.value} {f.unit} (conf={f.confidence:.2f})"
        )

    lines = []
    for cat, items in sorted(by_cat.items()):
        lines.append(f"\n[{cat}]")
        for item in items[:max_items // len(by_cat) if by_cat else max_items]:
            lines.append(f"  - {item}")
    return "\n".join(lines) if lines else "(no facts extracted)"


def _build_learned_context(mappings: list[LearnedMapping], max_items: int = 20) -> str:
    """Format learned mappings as LLM context."""
    if not mappings:
        return "(no learned mappings yet)"
    lines = []
    for m in mappings[:max_items]:
        lines.append(f"  - '{m.source_pattern}' → {m.canonical_term} [{m.category}] (accepted {m.acceptance_count}x)")
    return "\n".join(lines)


def _hash_prompt(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


async def run_enrichment(
    project_id: str,
    revision_id: str,
    facts: list[ExtractedFact],
    sources: list[SourceFile] | None = None,
    learned_mappings: list[LearnedMapping] | None = None,
    scope: str = "all",
) -> list[AiProposal]:
    """Run AI enrichment and return structured proposals.

    Raises RuntimeError if LLM is not configured.
    """
    if not settings.llm_available:
        raise RuntimeError(
            "LLM provider is not configured. Set OPENAI_API_KEY environment variable."
        )

    existing_cats = {f.category for f in facts}
    all_expected = {"area", "height", "setback", "parking", "dwelling_units",
                    "coverage", "floor_summary", "regulatory_threshold"}
    missing_cats = sorted(all_expected - existing_cats)

    if scope == "missing_only":
        relevant_facts = [f for f in facts if f.category in missing_cats]
    elif scope == "low_confidence":
        relevant_facts = [f for f in facts if f.confidence < 0.7]
    else:
        relevant_facts = facts

    doc_types = set()
    if sources:
        doc_types = {s.document_type for s in sources if s.document_type}

    user_prompt = _ENRICHMENT_USER_TEMPLATE.format(
        doc_types=", ".join(sorted(doc_types)) or "unknown",
        total_facts=len(facts),
        categories=", ".join(sorted(existing_cats)) or "none",
        missing=", ".join(missing_cats) or "none",
        facts_summary=_build_facts_summary(relevant_facts),
        learned_mappings=_build_learned_context(learned_mappings or []),
    )

    prompt_hash = _hash_prompt(user_prompt)

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.llm.api_key,
            timeout=settings.llm.timeout_seconds,
            max_retries=settings.llm.max_retries,
        )

        response = await client.chat.completions.create(
            model=settings.llm.model,
            messages=[
                {"role": "system", "content": _ENRICHMENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
            response_format={"type": "json_object"},
        )

        raw_text = response.choices[0].message.content or "[]"
        raw_data = json.loads(raw_text)

        if isinstance(raw_data, dict) and "proposals" in raw_data:
            raw_data = raw_data["proposals"]
        if not isinstance(raw_data, list):
            raw_data = [raw_data]

    except json.JSONDecodeError as exc:
        logger.error("LLM returned invalid JSON: %s", exc)
        return []
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        raise RuntimeError(f"LLM enrichment failed: {exc}") from exc

    proposals: list[AiProposal] = []
    for item in raw_data:
        if not isinstance(item, dict):
            continue
        proposal = AiProposal(
            project_id=project_id,
            revision_id=revision_id,
            source_document=item.get("source_document", ""),
            source_snippet=item.get("reasoning", ""),
            category=item.get("category", ""),
            label=item.get("label", ""),
            value=item.get("value"),
            unit=item.get("unit", ""),
            confidence=float(item.get("confidence", 0.0)),
            reasoning=item.get("reasoning", ""),
            model_version=settings.llm.model,
            prompt_hash=prompt_hash,
        )
        proposals.append(proposal)

    logger.info(
        "AI enrichment produced %d proposals for project=%s revision=%s",
        len(proposals), project_id, revision_id,
    )
    return proposals


def create_learning_event_from_decision(
    proposal: AiProposal,
    decision: str,
    user: str,
    edited_value: Any = None,
    edited_label: str = "",
) -> LearningEvent:
    """Create a learning event from a proposal decision."""
    event_type_map = {
        "accepted": LearningEventType.PROPOSAL_ACCEPTED,
        "rejected": LearningEventType.PROPOSAL_REJECTED,
        "edited": LearningEventType.PROPOSAL_EDITED,
    }
    event_type = event_type_map.get(decision, LearningEventType.MANUAL_CORRECTION)

    return LearningEvent(
        event_type=event_type,
        project_id=proposal.project_id,
        revision_id=proposal.revision_id,
        proposal_id=proposal.proposal_id,
        source_document=proposal.source_document,
        original_label=proposal.label,
        canonical_label=edited_label or proposal.label,
        original_value=proposal.value,
        corrected_value=edited_value if edited_value is not None else proposal.value,
        category=proposal.category,
        unit=proposal.unit,
        user=user,
    )
