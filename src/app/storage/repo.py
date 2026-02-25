"""Unified repository — delegates to pg_repo when DATABASE_URL is set, otherwise file_repo."""
from src.app.config import settings

if settings.use_postgres:
    from src.app.storage.pg_repo import (  # noqa: F401
        bootstrap_schema,
        compute_file_hash,
        get_project,
        get_revision,
        get_ruleset,
        get_source_file_path,
        get_validation,
        list_all_validations,
        list_projects,
        list_revisions,
        list_rulesets,
        list_validations_for_project,
        load_facts,
        load_findings,
        log_audit_event,
        report_path,
        save_facts,
        save_findings,
        save_project,
        save_revision,
        save_ruleset,
        save_validation,
        store_source_file,
    )
else:
    from src.app.storage.file_repo import (  # noqa: F401
        compute_file_hash,
        get_project,
        get_revision,
        get_ruleset,
        get_source_file_path,
        get_validation,
        list_all_validations,
        list_projects,
        list_revisions,
        list_rulesets,
        list_validations_for_project,
        load_facts,
        load_findings,
        log_audit_event,
        report_path,
        save_facts,
        save_findings,
        save_project,
        save_revision,
        save_ruleset,
        save_validation,
        store_source_file,
    )

    def bootstrap_schema() -> None:  # noqa: F811
        pass
