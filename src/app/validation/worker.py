"""Async validation worker — picks jobs from an in-memory queue and executes them."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from src.app.domain.models import ValidationStatus
from src.app.storage import file_repo
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
        run = file_repo.get_validation(validation_id)
        if not run:
            logger.error("Validation %s not found", validation_id)
            return

        run.status = ValidationStatus.RUNNING
        run.started_at = datetime.utcnow()
        file_repo.save_validation(run)
        file_repo.log_audit_event("start", "validation", validation_id)

        ruleset = file_repo.get_ruleset(run.ruleset_id)
        if not ruleset:
            await self._mark_failed(validation_id, f"RuleSet {run.ruleset_id} not found")
            return

        facts = file_repo.load_facts(run.project_id, run.revision_id)
        if not facts:
            logger.warning("No facts for revision %s — validation will produce zero findings", run.revision_id)

        findings = evaluate_ruleset(
            ruleset=ruleset,
            facts=facts,
            project_id=run.project_id,
            revision_id=run.revision_id,
            validation_id=validation_id,
        )

        file_repo.save_findings(validation_id, findings)

        try:
            generate_pdf_report(validation_id, run, findings)
        except Exception as exc:
            logger.warning("PDF report generation failed (non-blocking): %s", exc)

        run = file_repo.get_validation(validation_id)
        run.status = ValidationStatus.DONE
        run.completed_at = datetime.utcnow()
        run.findings_count = len(findings)
        file_repo.save_validation(run)
        file_repo.log_audit_event("complete", "validation", validation_id, {"findings": len(findings)})

        logger.info("Validation %s completed with %d findings", validation_id, len(findings))

    async def _mark_failed(self, validation_id: str, error: str):
        run = file_repo.get_validation(validation_id)
        if run:
            run.status = ValidationStatus.FAILED
            run.completed_at = datetime.utcnow()
            run.error_message = error
            file_repo.save_validation(run)
            file_repo.log_audit_event("failed", "validation", validation_id, {"error": error})


validation_manager = ValidationManager()
