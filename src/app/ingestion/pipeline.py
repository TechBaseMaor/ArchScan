"""Ingestion pipeline — dispatches source files to appropriate adapters and persists extracted facts.

Includes an officiality verification gate for regulation documents: files below
the auto-approve threshold are flagged for manual review and excluded from
auto-scoring comparisons until approved.
"""
from __future__ import annotations

import logging
from typing import List

from src.app.domain.models import (
    DocumentRole,
    ExtractedFact,
    OfficialityStatus,
    ReviewItem,
    Revision,
    SourceFormat,
)
from src.app.storage import repo
from src.app.ingestion.ifc_adapter import extract_facts_from_ifc
from src.app.ingestion.pdf_adapter import extract_facts_from_pdf
from src.app.ingestion.dwfx_adapter import extract_facts_from_dwfx
from src.app.ingestion.bundle_classifier import classify_source
from src.app.ingestion.officiality_verifier import verify_officiality

logger = logging.getLogger(__name__)


async def run_ingestion(project_id: str, revision: Revision) -> list[ExtractedFact]:
    all_facts: list[ExtractedFact] = []
    review_items: List[ReviewItem] = []

    for source in revision.sources:
        if source.document_role == DocumentRole.UNKNOWN:
            role, doc_type = classify_source(source)
            source.document_role = role
            source.document_type = doc_type

        source, review_item = verify_officiality(source, project_id, revision.revision_id)
        if review_item is not None:
            review_items.append(review_item)

        if (
            source.document_role == DocumentRole.REGULATION
            and source.officiality_status == OfficialityStatus.UNVERIFIED
        ):
            logger.warning(
                "Skipping fact extraction for unverified regulation doc %s "
                "(awaiting manual review)",
                source.file_name,
            )
            continue

        adapter_facts: list[ExtractedFact] = []

        if source.source_format == SourceFormat.IFC:
            adapter_facts = extract_facts_from_ifc(
                source.stored_path, revision.revision_id, source.source_hash
            )
        elif source.source_format == SourceFormat.PDF:
            adapter_facts = extract_facts_from_pdf(
                source.stored_path, revision.revision_id, source.source_hash,
                document_role=source.document_role,
            )
        elif source.source_format == SourceFormat.DWFX:
            adapter_facts = extract_facts_from_dwfx(
                source.stored_path, revision.revision_id, source.source_hash,
                document_role=source.document_role,
            )
        else:
            logger.warning("No adapter for format %s — skipping %s", source.source_format, source.file_name)

        for fact in adapter_facts:
            fact.metadata.setdefault("doc_role", source.document_role.value)
            fact.metadata.setdefault("doc_type", source.document_type)
            fact.metadata.setdefault("source_file", source.file_name)
            fact.metadata.setdefault("officiality", source.officiality_status.value)

        all_facts.extend(adapter_facts)

    for item in review_items:
        repo.save_review_item(item)

    repo.save_facts(project_id, revision.revision_id, all_facts)
    repo.log_audit_event(
        "ingestion_complete",
        "revision",
        revision.revision_id,
        {
            "project_id": project_id,
            "facts_extracted": len(all_facts),
            "review_items_created": len(review_items),
        },
    )

    logger.info(
        "Ingestion complete for revision %s: %d facts, %d review items",
        revision.revision_id, len(all_facts), len(review_items),
    )
    return all_facts
