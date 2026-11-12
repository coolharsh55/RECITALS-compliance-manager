"""Requirement-level results (passed / failed / warning) and the /ui page."""
from pathlib import Path

import pytest

from test_examples import CASES, IDS, run

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.mark.parametrize("name,law,article,_ids", CASES, ids=IDS)
def test_compliant_example_passes_every_requirement(services, name, law, article, _ids):
    """Compliant example passes every requirement."""
    body = run(services, law, article, EXAMPLES / f"{name}_compliant.ttl")
    statuses = {r["id"]: r["status"] for r in body["requirements"]}
    assert statuses and set(statuses.values()) == {"passed"}, statuses
    assert body["summary"] == {"total": len(statuses), "passed": len(statuses), "failed": 0, "warnings": 0}


@pytest.mark.parametrize("name,law,article,ids", CASES, ids=IDS)
def test_noncompliant_example_marks_exactly_its_findings(services, name, law, article, ids):
    """Noncompliant example marks exactly its findings."""
    body = run(services, law, article, EXAMPLES / f"{name}_noncompliant.ttl")
    requirements = {r["id"]: r for r in body["requirements"]}
    not_passed = {i for i, r in requirements.items() if r["status"] != "passed"}
    assert not_passed == ids
    for requirement in requirements.values():
        obligations = {f["obligation"] for f in requirement["findings"]}
        expected = "failed" if "mandatory" in obligations else "warning" if obligations else "passed"
        assert requirement["status"] == expected, requirement
    summary = body["summary"]
    assert summary["passed"] + summary["failed"] + summary["warnings"] == summary["total"] == len(requirements)
    assert summary["passed"] > 0  # the rest of the article's requirements are reported as met


def test_warning_only_requirement_is_a_warning(services):
    """A requirement with only Warning findings is marked warning."""
    body = run(services, "NIS2", 21, EXAMPLES / "nis2_21_noncompliant.ttl")
    status = {r["id"]: r["status"] for r in body["requirements"]}
    assert status["N21-2-b"] == "failed"
    assert status["N21-3-1"] == "warning"
    assert status["N21-2-a-2"] == "passed"


def test_report_recomputes_requirements(services):
    """Report recomputes requirements."""
    body = run(services, "GDPR", 32, EXAMPLES / "gdpr32_noncompliant.ttl")
    report = services["compliance-api"].get(f"/assessments/{body['assessment_id']}/report").json()
    as_status = lambda reqs: {r["id"]: r["status"] for r in reqs}
    assert as_status(report["requirements"]) == as_status(body["requirements"])
    assert report["requirement_summary"] == body["summary"]


def test_ui_page_is_served(services):
    """/ui page is served."""
    r = services["compliance-api"].get("/ui")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "Run check" in r.text
    assert "__INPUT_API_URL__" not in r.text and "http://localhost:8000" in r.text


def test_input_api_allows_uploads_from_the_ui(services):
    """The Input API allows uploads from the /ui page (CORS)."""
    r = services["input-api"].options(
        "/input",
        headers={"Origin": "http://localhost:8001", "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:8001"


def test_stored_assessment_of_retired_article_still_displays(services):
    """NIS2 Art. 22 was replaced by Art. 21; assessments already stored for it must still show."""
    from conftest import load_service
    services["input-api"].post("/use-cases", data={"use_case_id": "UC1", "law": "NIS2", "label": "x"})
    compliance = load_service("compliance-api")
    old_id, _ = compliance.store_result(
        use_case_id="UC1", law=compliance.Law.NIS2, article=22, conforms=False,
        findings=[{"requirement_ids": ["N22-2"], "message": "old finding", "severity": "Violation",
                   "focus_node": "http://example.com/Acme", "property": None}],
    )
    history = services["compliance-api"].get("/use-cases/UC1/assessments").json()
    assert [(a["law"], a["article"]) for a in history] == [("NIS2", 22)]
    report = services["compliance-api"].get(f"/assessments/{old_id}/report")
    assert report.status_code == 200, report.text
    body = report.json()
    assert [(r["id"], r["status"]) for r in body["requirements"]] == [("N22-2", "failed")]
    assert body["requirement_summary"] == {"total": 1, "passed": 0, "failed": 1, "warnings": 0}
