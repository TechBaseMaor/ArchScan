"""Unit tests for the file repository."""
import pytest
import shutil
from pathlib import Path

from src.app.config import settings
from src.app.domain.models import (
    ExtractedFact,
    FactType,
    Finding,
    ComputationTrace,
    Project,
    Revision,
    RuleSet,
    Severity,
    ValidationRun,
)
from src.app.storage import file_repo


@pytest.fixture(autouse=True)
def clean_data(tmp_path):
    """Redirect data and rulesets dirs to temp for each test."""
    settings.data_dir = tmp_path / "data"
    settings.rulesets_dir = tmp_path / "rulesets"
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.rulesets_dir.mkdir(parents=True, exist_ok=True)
    yield
    settings.data_dir = Path("data")
    settings.rulesets_dir = Path("rulesets")


class TestProjectCRUD:
    def test_create_and_get(self):
        p = Project(name="Test Project")
        file_repo.save_project(p)
        loaded = file_repo.get_project(p.project_id)
        assert loaded is not None
        assert loaded.name == "Test Project"

    def test_get_nonexistent(self):
        assert file_repo.get_project("nonexistent") is None

    def test_list_projects(self):
        file_repo.save_project(Project(name="A"))
        file_repo.save_project(Project(name="B"))
        projects = file_repo.list_projects()
        assert len(projects) == 2


class TestRevisionAppendOnly:
    def test_create_revision(self):
        p = Project(name="P1")
        file_repo.save_project(p)
        r = Revision(project_id=p.project_id)
        file_repo.save_revision(r)
        loaded = file_repo.get_revision(p.project_id, r.revision_id)
        assert loaded is not None

    def test_overwrite_forbidden(self):
        p = Project(name="P2")
        file_repo.save_project(p)
        r = Revision(project_id=p.project_id)
        file_repo.save_revision(r)
        with pytest.raises(ValueError, match="already exists"):
            file_repo.save_revision(r)


class TestSourceFile:
    def test_store_and_retrieve(self):
        p = Project(name="P")
        file_repo.save_project(p)
        content = b"test file content"
        source_hash, stored_path = file_repo.store_source_file(p.project_id, "test.ifc", content)
        assert len(source_hash) == 16
        assert Path(stored_path).exists()

    def test_hash_determinism(self):
        p = Project(name="P")
        file_repo.save_project(p)
        content = b"same content"
        h1, _ = file_repo.store_source_file(p.project_id, "a.ifc", content)
        h2 = file_repo.compute_file_hash(content)
        assert h1 == h2


class TestValidationPersistence:
    def test_save_and_load(self):
        v = ValidationRun(project_id="p1", revision_id="r1", ruleset_id="rs1")
        file_repo.save_validation(v)
        loaded = file_repo.get_validation(v.validation_id)
        assert loaded is not None
        assert loaded.project_id == "p1"


class TestFindingsPersistence:
    def test_save_and_load(self):
        f = Finding(
            validation_id="v1",
            rule_ref="R1:1.0",
            severity=Severity.ERROR,
            message="test",
            input_facts=["f1"],
            computation_trace=ComputationTrace(formula="test", inputs={"a": 1}),
            project_id="p1",
            revision_id="r1",
        )
        file_repo.save_findings("v1", [f])
        loaded = file_repo.load_findings("v1")
        assert len(loaded) == 1
        assert loaded[0].rule_ref == "R1:1.0"


class TestRuleSetPersistence:
    def test_save_and_get_latest(self):
        rs = RuleSet(ruleset_id="rs1", name="Test Rules", version="1.0.0")
        file_repo.save_ruleset(rs)
        loaded = file_repo.get_ruleset("rs1")
        assert loaded is not None
        assert loaded.version == "1.0.0"

    def test_get_specific_version(self):
        rs1 = RuleSet(ruleset_id="rs2", name="Rules", version="1.0.0")
        rs2 = RuleSet(ruleset_id="rs2", name="Rules", version="2.0.0")
        file_repo.save_ruleset(rs1)
        file_repo.save_ruleset(rs2)
        loaded = file_repo.get_ruleset("rs2", "1.0.0")
        assert loaded.version == "1.0.0"
