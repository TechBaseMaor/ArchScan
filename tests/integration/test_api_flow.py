"""Integration test — full end-to-end API flow with synthetic data."""
import asyncio
import json
import io
import pytest
from pathlib import Path

from httpx import AsyncClient, ASGITransport
from src.app.main import app
from src.app.config import settings


@pytest.fixture(autouse=True)
def setup_env(tmp_path):
    old_data = settings.data_dir
    old_rulesets = settings.rulesets_dir
    old_upload = settings.upload_dir

    settings.data_dir = tmp_path / "data"
    settings.rulesets_dir = tmp_path / "rulesets"
    settings.upload_dir = tmp_path / "data" / "uploads"
    for d in [
        settings.data_dir / "projects",
        settings.data_dir / "validations",
        settings.data_dir / "findings",
        settings.data_dir / "reports",
        settings.data_dir / "audit",
        settings.upload_dir,
        settings.rulesets_dir,
    ]:
        d.mkdir(parents=True, exist_ok=True)
    yield
    settings.data_dir = old_data
    settings.rulesets_dir = old_rulesets
    settings.upload_dir = old_upload


@pytest.mark.asyncio
async def test_full_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        r = await client.get("/health")
        assert r.status_code == 200

        # 2. Create project
        r = await client.post("/projects", json={"name": "Test Building", "description": "Integration test"})
        assert r.status_code == 200
        project = r.json()
        project_id = project["project_id"]

        # 3. Create a ruleset
        ruleset_payload = {
            "ruleset_id": "test-rules",
            "name": "Test Rules",
            "version": "1.0.0",
            "rules": [
                {
                    "rule_id": "TEST-AREA-MAX",
                    "version": "1.0",
                    "severity": "error",
                    "preconditions": [{"fact_category": "area", "operator": "exists"}],
                    "computation": {"formula": "area_max_check", "parameters": {"max_area": 100}},
                },
                {
                    "rule_id": "TEST-HEIGHT-MIN",
                    "version": "1.0",
                    "severity": "error",
                    "preconditions": [{"fact_category": "height", "operator": "exists"}],
                    "computation": {"formula": "height_min_check", "parameters": {"min_height": 2.5}},
                },
            ],
        }
        r = await client.post("/rulesets", json=ruleset_payload)
        assert r.status_code == 200

        # 4. Get ruleset
        r = await client.get("/rulesets/test-rules")
        assert r.status_code == 200
        assert r.json()["name"] == "Test Rules"

        # 5. Upload revision with a synthetic PDF
        pdf_content = b"%PDF-1.4 area: 150 m2 height: 2.0 m setback: 2.5 m"
        files = [("files", ("plan.pdf", io.BytesIO(pdf_content), "application/pdf"))]
        r = await client.post(
            f"/projects/{project_id}/revisions",
            files=files,
            data={"metadata": json.dumps({"test": True})},
        )
        assert r.status_code == 200
        revision = r.json()
        revision_id = revision["revision_id"]

        # 6. Start validation (runs inline since worker isn't started in test)
        r = await client.post("/validations", json={
            "project_id": project_id,
            "revision_id": revision_id,
            "ruleset_id": "test-rules",
        })
        assert r.status_code == 200
        validation = r.json()
        validation_id = validation["validation_id"]

        # 7. Check validation status — should be done (ran inline)
        r = await client.get(f"/validations/{validation_id}")
        assert r.status_code == 200
        val_result = r.json()
        assert val_result["status"] == "done", (
            f"Validation ended with status={val_result['status']}, error={val_result.get('error_message')}"
        )

        # 8. Check findings have full traceability
        r = await client.get(f"/validations/{validation_id}/findings")
        assert r.status_code == 200
        findings = r.json()
        assert isinstance(findings, list)

        for finding in findings:
            assert "rule_ref" in finding
            assert ":" in finding["rule_ref"]
            assert "input_facts" in finding
            assert "computation_trace" in finding
            assert "project_id" in finding
            assert "revision_id" in finding

        # 9. Check revision facts endpoint
        r = await client.get(f"/projects/{project_id}/revisions/{revision_id}/facts")
        assert r.status_code == 200
        facts = r.json()
        assert isinstance(facts, list)
        assert len(facts) > 0
        for fact in facts:
            assert "fact_id" in fact
            assert "category" in fact
            assert "value" in fact
            assert "confidence" in fact
            assert "metadata" in fact

        # 10. Check revision summary endpoint
        r = await client.get(f"/projects/{project_id}/revisions/{revision_id}/summary")
        assert r.status_code == 200
        summary = r.json()
        assert summary["project_id"] == project_id
        assert summary["revision_id"] == revision_id
        assert summary["total_facts"] > 0
        assert isinstance(summary["areas"], list)
        assert isinstance(summary["heights"], list)
        assert isinstance(summary["reconciliation"], list)
        for area_metric in summary["areas"]:
            assert "label" in area_metric
            assert "value" in area_metric
            assert "confidence" in area_metric
            assert "source" in area_metric

        # 11. Check project history
        r = await client.get(f"/projects/{project_id}/history")
        assert r.status_code == 200
        history = r.json()
        assert len(history) >= 1
        assert history[0]["revision_id"] == revision_id


@pytest.mark.asyncio
async def test_list_rulesets():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/rulesets", json={
            "ruleset_id": "rs1", "name": "RS1", "version": "1.0.0", "rules": [],
        })
        assert r.status_code == 200

        r = await client.get("/rulesets")
        assert r.status_code == 200
        assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_demo_bootstrap():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/demo/bootstrap")
        assert r.status_code == 200
        project = r.json()
        assert "project_id" in project
        assert project["name"]

        project_id = project["project_id"]
        r = await client.get(f"/projects/{project_id}/revisions")
        assert r.status_code == 200
        revisions = r.json()
        assert len(revisions) == 1

        revision_id = revisions[0]["revision_id"]
        r = await client.get(f"/projects/{project_id}/revisions/{revision_id}/summary")
        assert r.status_code == 200
        summary = r.json()
        assert summary["total_facts"] > 0
        assert len(summary["areas"]) > 0
        assert len(summary["heights"]) > 0
        assert len(summary["openings"]) > 0
        assert len(summary["setbacks"]) > 0


@pytest.mark.asyncio
async def test_demo_samples_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/demo/samples")
        assert r.status_code == 200
        samples = r.json()
        assert isinstance(samples, list)
        assert len(samples) >= 1
        assert "name" in samples[0]
        assert "download_url" in samples[0]


@pytest.mark.asyncio
async def test_compliance_report_endpoint():
    """Integration test: compliance report includes extracted_metrics and missing_evidence."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/projects", json={"name": "Compliance Test"})
        project_id = r.json()["project_id"]

        r = await client.post("/rulesets", json={
            "ruleset_id": "compliance-rs",
            "name": "Compliance RS",
            "version": "1.0.0",
            "rules": [{
                "rule_id": "C-AREA",
                "version": "1.0",
                "severity": "error",
                "preconditions": [{"fact_category": "area", "operator": "exists"}],
                "computation": {"formula": "area_max_check", "parameters": {"max_area": 500}},
                "metadata": {"layer": "statutory"},
            }],
        })

        pdf_content = b"%PDF-1.4 area: 150 m2"
        files = [("files", ("plan.pdf", io.BytesIO(pdf_content), "application/pdf"))]
        r = await client.post(f"/projects/{project_id}/revisions", files=files)
        revision_id = r.json()["revision_id"]

        r = await client.post("/validations", json={
            "project_id": project_id,
            "revision_id": revision_id,
            "ruleset_id": "compliance-rs",
        })
        validation_id = r.json()["validation_id"]

        r = await client.get(f"/validations/{validation_id}")
        assert r.json()["status"] == "done"

        r = await client.get(f"/validations/{validation_id}/compliance")
        assert r.status_code == 200
        report = r.json()

        assert "extracted_metrics" in report
        assert "missing_evidence" in report
        assert "document_coverage" in report
        assert "missing_documents" in report
        assert isinstance(report["extracted_metrics"], list)
        assert isinstance(report["missing_evidence"], list)

        for m in report["extracted_metrics"]:
            if m["is_missing"]:
                assert m["value"] is None
                assert m["missing_reason"] != ""


@pytest.mark.asyncio
async def test_list_validations_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/validations")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_project_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/projects/nonexistent")
        assert r.status_code == 404
