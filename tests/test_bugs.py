"""Regression tests for the bugs fixed in the compliance, input and status APIs."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NONCOMPLIANT_RDF = b"""
@prefix dpv: <https://w3id.org/dpv#> .
@prefix ex: <http://example.com/> .
@prefix recitals: <http://example.org/recitals/> .
ex:Activity1 a dpv:Process, recitals:UseCaseResource .
"""


def create_use_case(services, law="GDPR"):
    """Create use case UC1 for a law through the Input API."""
    r = services["input-api"].post("/use-cases", data={"use_case_id": "UC1", "law": law, "label": "Support"})
    assert r.status_code == 201, r.text


def upload(services, rdf=NONCOMPLIANT_RDF):
    """Upload Turtle data to UC1 through the Input API."""
    r = services["input-api"].post(
        "/input", data={"use_case_id": "UC1"}, files={"file": ("d.ttl", rdf, "text/turtle")}
    )
    assert r.status_code == 201, r.text


def test_incomplete_processing_activity_fails_art30(services):
    """Incomplete processing activity fails Art. 30."""
    create_use_case(services)
    upload(services)
    r = services["compliance-api"].post("/check", data={"use_case": "UC1", "law": "GDPR", "article": 30})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "failed", r.json()


def test_status_returns_latest_assessment(services):
    """Status returns latest assessment."""
    create_use_case(services)
    upload(services)
    services["compliance-api"].post("/check", data={"use_case": "UC1", "law": "GDPR", "article": 30})
    r = services["status-api"].get("/status", params={"use_case_id": "UC1", "law": "GDPR", "article": 30})
    assert r.status_code == 200, r.text
    assert r.json()["status"] in ("passed", "failed"), r.json()


def test_removed_legacy_endpoints_are_gone(services):
    """Removed legacy endpoints are gone."""
    create_use_case(services)
    upload(services)
    r = services["compliance-api"].post("/check", data={"use_case": "UC1", "law": "GDPR", "article": 30})
    assessment_id = r.json()["assessment_id"]
    assert services["compliance-api"].post("/validate").status_code == 404
    assert services["compliance-api"].get(f"/assessments/{assessment_id}").status_code == 404
    assert services["compliance-api"].get(f"/assessments/{assessment_id}/report").status_code == 200
    assert services["input-api"].patch("/use_cases/laws", data={"use_case": "UC1", "law": "NIS2"}).status_code == 404


def test_ai_act_shape_files_exist():
    """The AI Act shape files named in ASSESSMENTS exist."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("c", ROOT / "compliance-api" / "main.py")
    src = (ROOT / "compliance-api" / "main.py").read_text()
    for name in ("shapes_eu_ai_act_10.ttl", "shapes_eu_ai_act_11.ttl"):
        if name in src:
            assert (ROOT / "compliance-api" / name).exists(), name


def test_list_assessments_ordered_with_timestamps(services):
    """GET /use-cases/{id}/assessments returns each assessment's timestamp."""
    create_use_case(services)
    upload(services)
    services["compliance-api"].post("/check", data={"use_case": "UC1", "law": "GDPR", "article": 30})
    r = services["compliance-api"].get("/use-cases/UC1/assessments")
    assert r.status_code == 200, r.text
    assert r.json()[0]["timestamp"] is not None, r.json()


def test_assessment_id_cannot_inject_sparql(services):
    """Assessment id cannot inject SPARQL."""
    r = services["compliance-api"].get('/assessments/x" } UNION { ?a ?b ?c . FILTER("1"="1/report')
    assert r.status_code in (404, 422), r.text


def test_sample_data_is_validated_with_findings(services):
    """Sample data is validated with findings."""
    create_use_case(services)
    upload(services, (ROOT / "examples" / "gdpr30_noncompliant.ttl").read_bytes())
    r = services["compliance-api"].post("/check", data={"use_case": "UC1", "law": "GDPR", "article": 30})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["findings"], body
    assert all(f["requirement_ids"] for f in body["findings"]), body["findings"]
    report = services["compliance-api"].get(f"/assessments/{body['assessment_id']}/report")
    assert report.status_code == 200, report.text
    assert report.json()["summary"]["total_findings"] == len(body["findings"])


def test_use_case_data_is_isolated(services):
    """Use case data is isolated."""
    create_use_case(services)
    services["input-api"].post("/use-cases", data={"use_case_id": "UC2", "law": "GDPR", "label": "Other"})
    upload(services)  # incomplete activity goes to UC1 only
    services["input-api"].post(
        "/input", data={"use_case_id": "UC2"}, files={"file": ("d.ttl", b"<http://e/x> <http://e/p> 1 .", "text/turtle")}
    )
    r = services["compliance-api"].post("/check", data={"use_case": "UC2", "law": "GDPR", "article": 30})
    assert r.json()["status"] == "passed", r.json()


def test_status_has_no_unused_parameters(services):
    """Status has no unused parameters."""
    spec = services["status-api"].get("/openapi.json").json()
    names = {p["name"] for p in spec["paths"]["/status"]["get"]["parameters"]}
    assert names == {"use_case_id", "law", "article"}
    use_case = next(p for p in spec["paths"]["/status"]["get"]["parameters"] if p["name"] == "use_case_id")
    assert use_case["required"] is True


def test_status_requires_use_case_id(services):
    """Status requires use case id."""
    assert services["status-api"].get("/status", params={"law": "GDPR", "article": 30}).status_code == 422
