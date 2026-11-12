"""Use case ids are chosen by the client, validated, and unique."""
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def create(services, use_case_id, law="EU_AI_ACT"):
    """Create a use case through the Input API and return the response."""
    return services["input-api"].post("/use-cases", data={"use_case_id": use_case_id, "law": law, "label": "x"})


def test_custom_id_end_to_end(services):
    """A client-chosen use case id works for create, upload, check, status and history."""
    assert create(services, "hr-screening_2026").status_code == 201
    r = services["input-api"].post(
        "/input", data={"use_case_id": "hr-screening_2026"},
        files={"file": ("d.ttl", (EXAMPLES / "eu_ai_act_10_compliant.ttl").read_bytes(), "text/turtle")},
    )
    assert r.status_code == 201, r.text
    r = services["compliance-api"].post("/check", data={"use_case": "hr-screening_2026", "law": "EU_AI_ACT", "article": 10})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "passed"
    listed = [u["use_case_id"] for u in services["compliance-api"].get("/use-cases").json()]
    assert "hr-screening_2026" in listed
    r = services["status-api"].get("/status", params={"use_case_id": "hr-screening_2026", "law": "EU_AI_ACT", "article": 10})
    assert r.json()["status"] == "passed"
    assert services["compliance-api"].get("/use-cases/hr-screening_2026/assessments").json()


@pytest.mark.parametrize("bad", ["has space", "x>y", "a/b", "1starts-with-digit", "x" * 81, ""])
def test_unsafe_id_is_rejected(services, bad):
    """Unsafe id is rejected."""
    assert create(services, bad).status_code == 422


@pytest.mark.parametrize("bad", ["has space", "x>y", 'x" } UNION {'])
def test_unsafe_id_is_rejected_by_check(services, bad):
    """Unsafe id is rejected by check."""
    r = services["compliance-api"].post("/check", data={"use_case": bad, "law": "GDPR", "article": 30})
    assert r.status_code == 422


def test_duplicate_id_is_a_conflict(services):
    """Duplicate id is a conflict."""
    assert create(services, "TRIAGE").status_code == 201
    r = create(services, "TRIAGE", law="GDPR")
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]
    laws = services["compliance-api"].get("/use-cases/TRIAGE/laws").json()
    assert laws == ["EU_AI_ACT"]  # the duplicate did not change the use case


def test_law_can_be_added_to_existing_use_case(services):
    """Law can be added to existing use case."""
    assert create(services, "TRIAGE").status_code == 201
    r = services["input-api"].patch("/use-cases/TRIAGE/laws", data={"law": "GDPR"})
    assert r.status_code == 200, r.text
    assert sorted(services["compliance-api"].get("/use-cases/TRIAGE/laws").json()) == ["EU_AI_ACT", "GDPR"]


def test_unknown_use_case_is_not_found(services):
    """Unknown use case is not found."""
    r = services["compliance-api"].post("/check", data={"use_case": "NOPE", "law": "GDPR", "article": 30})
    assert r.status_code == 404
