"""Ingestion pipeline — dispatches source files to appropriate adapters and persists extracted facts."""
from __future__ import annotations

import logging

from src.app.domain.models import Revision, SourceFormat, ExtractedFact
from src.app.storage import repo
from src.app.ingestion.ifc_adapter import extract_facts_from_ifc
from src.app.ingestion.pdf_adapter import extract_facts_from_pdf

logger = logging.getLogger(__name__)


async def run_ingestion(project_id: str, revision: Revision) -> list[ExtractedFact]:
    all_facts: list[ExtractedFact] = []

    for source in revision.sources:
        adapter_facts: list[ExtractedFact] = []

        if source.source_format == SourceFormat.IFC:
            adapter_facts = extract_facts_from_ifc(
                source.stored_path, revision.revision_id, source.source_hash
            )
        elif source.source_format == SourceFormat.PDF:
            adapter_facts = extract_facts_from_pdf(
                source.stored_path, revision.revision_id, source.source_hash
            )
        else:
            logger.warning("No adapter for format %s — skipping %s", source.source_format, source.file_name)

        all_facts.extend(adapter_facts)

    repo.save_facts(project_id, revision.revision_id, all_facts)
    repo.log_audit_event(
        "ingestion_complete",
        "revision",
        revision.revision_id,
        {"project_id": project_id, "facts_extracted": len(all_facts)},
    )

    logger.info("Ingestion complete for revision %s: %d facts", revision.revision_id, len(all_facts))
    return all_facts
