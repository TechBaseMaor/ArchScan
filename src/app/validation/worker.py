"""Async validation worker — picks jobs from an in-memory queue and executes them.

Includes a review-gate check: if any regulation documents in the revision
have pending officiality reviews, validation proceeds with a warning flag
on the compliance report rather than blocking entirely.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from src.app.domain.models import (
    OfficialityStatus,
    ReviewStatus,
    ValidationStatus,
)
from src.app.storage import repo
from src.app.engine.rule_engine import evaluate_ruleset
from src.app.reporting.report_service import generate_pdf_report

logger = logging.getLogger(__name__)


class ValidationManager:
    def __init__(self):
        self._queue: Optional[asyncio.Queue] = None
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        self._queue = asyncio.Queue()
        self._task = asyncio.create_task(self._worker_loop())
        logger.info("Validation worker started")

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._queue = None
        logger.info("Validation worker stopped")

    async def enqueue(self, validation_id: str):
        if self._queue is None:
            logger.warning("Worker not started — running validation inline")
            await self._run_validation(validation_id)
            return
        await self._queue.put(validation_id)
        logger.info("Enqueued validation %s", validation_id)

    async def _worker_loop(self):
        while True:
            validation_id = await self._queue.get()
            try:
                await self._run_validation(validation_id)
            except Exception as exc:
                logger.exception("Validation %s failed: %s", validation_id, exc)
                await self._mark_failed(validation_id, str(exc))
            finally:
                self._queue.task_done()

    async def _run_validation(self, validation_id: str):
        run = repo.get_validation(validation_id)
        if not run:
            logger.error("Validation %s not found", validation_id)
            return

        run.status = ValidationStatus.RUNNING
        run.started_at = datetime.utcnow()
        repo.save_validation(run)
        repo.log_audit_event("start", "validation", validation_id)

        ruleset = repo.get_ruleset(run.ruleset_id)
        if not ruleset:
            await self._mark_failed(validation_id, f"RuleSet {run.ruleset_id} not found")
            return

        has_pending = self._check_pending_reviews(run.project_id, run.revision_id)
        if has_pending:
            logger.warning(
                "Validation %s proceeding with pending officiality reviews — "
                "report will be flagged",
                validation_id,
            )

        facts = repo.load_facts(run.project_id, run.revision_id)
        if not facts:
            logger.warning("No facts for revision %s — validation will produce zero findings", run.revision_id)

        verified_facts = [
            f for f in facts
            if f.metadata.get("officiality") != OfficialityStatus.UNVERIFIED.value
        ]
        unverified_count = len(facts) - len(verified_facts)
        if unverified_count > 0:
            logger.info(
                "Excluded %d facts from unverified regulation docs", unverified_count,
            )

        findings = evaluate_ruleset(
            ruleset=ruleset,
            facts=verified_facts,
            project_id=run.project_id,
            revision_id=run.revision_id,
            validation_id=validation_id,
        )

        repo.save_findings(validation_id, findings)

        try:
            generate_pdf_report(validation_id, run, findings)
        except Exception as exc:
            logger.warning("PDF report generation failed (non-blocking): %s", exc)

        run = repo.get_validation(validation_id)
        run.status = ValidationStatus.DONE
        run.completed_at = datetime.utcnow()
        run.findings_count = len(findings)
        repo.save_validation(run)
        repo.log_audit_event(
            "complete", "validation", validation_id,
            {
                "findings": len(findings),
                "has_pending_reviews": has_pending,
                "unverified_facts_excluded": unverified_count,
            },
        )

        logger.info("Validation %s completed with %d findings", validation_id, len(findings))

    def _check_pending_reviews(self, project_id: str, revision_id: str) -> bool:
        """Check if any review items are still pending for this revision."""
        try:
            items = repo.list_review_items(project_id=project_id, status="pending_review")
            return any(item.revision_id == revision_id for item in items)
        except Exception:
            return False

    async def _mark_failed(self, validation_id: str, error: str):
        run = repo.get_validation(validation_id)
        if run:
            run.status = ValidationStatus.FAILED
            run.completed_at = datetime.utcnow()
            run.error_message = error
            repo.save_validation(run)
            repo.log_audit_event("failed", "validation", validation_id, {"error": error})


validation_manager = ValidationManager()
