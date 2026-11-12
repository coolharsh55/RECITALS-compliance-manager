"""/docs offers existing use cases as dropdowns; unknown use cases are 404 everywhere."""
import pytest


def create(services, use_case_id, law="GDPR"):
    """Create a use case through the Input API and return the response."""
    r = services["input-api"].post("/use-cases", data={"use_case_id": use_case_id, "law": law, "label": "x"})
    assert r.status_code == 201, r.text


def field(spec, path, method, name):
    """Return a parameter or form field schema from an OpenAPI document."""
    operation = spec["paths"][path][method]
    for parameter in operation.get("parameters", []):
        if parameter["name"] == name:
            return parameter["schema"]
    ref = operation["requestBody"]["content"]["application/x-www-form-urlencoded"]["schema"]["$ref"]
    return spec["components"]["schemas"][ref.rsplit("/", 1)[-1]]["properties"][name]


DROPDOWNS = [
    ("input-api", "/input", "post", "use_case_id"),
    ("input-api", "/use-cases/{use_case_id}/laws", "patch", "use_case_id"),
    ("compliance-api", "/check", "post", "use_case"),
    ("compliance-api", "/use-cases/{use_case_id}/assessments", "get", "use_case_id"),
    ("compliance-api", "/use-cases/{use_case_id}/laws", "get", "use_case_id"),
    ("status-api", "/status", "get", "use_case_id"),
]


def get_field(services, service, path, method, name):
    """Return a field schema from a service's /openapi.json."""
    spec = services[service].get("/openapi.json").json()
    try:
        return field(spec, path, method, name)
    except KeyError:  # multipart form (file upload)
        operation = spec["paths"][path][method]
        ref = operation["requestBody"]["content"]["multipart/form-data"]["schema"]["$ref"]
        return spec["components"]["schemas"][ref.rsplit("/", 1)[-1]]["properties"][name]


@pytest.mark.parametrize("service,path,method,name", DROPDOWNS, ids=[f"{d[0]} {d[2]} {d[1]}" for d in DROPDOWNS])
def test_existing_use_cases_are_a_dropdown(services, service, path, method, name):
    """Existing use cases are a dropdown."""
    create(services, "TRIAGE")
    create(services, "hr-screening", law="EU_AI_ACT")
    assert get_field(services, service, path, method, name)["enum"] == ["TRIAGE", "hr-screening"]


def test_new_use_case_appears_without_restart(services):
    """New use case appears without restart."""
    create(services, "TRIAGE")
    assert get_field(services, "compliance-api", "/check", "post", "use_case")["enum"] == ["TRIAGE"]
    create(services, "WATER", law="NIS2")
    assert get_field(services, "compliance-api", "/check", "post", "use_case")["enum"] == ["TRIAGE", "WATER"]


def test_creating_a_use_case_stays_free_text(services):
    """Creating a use case stays free text."""
    create(services, "TRIAGE")
    schema = get_field(services, "input-api", "/use-cases", "post", "use_case_id")
    assert "enum" not in schema and schema["type"] == "string"


def test_no_use_cases_yet_gives_free_text(services):
    """No use cases yet gives free text."""
    assert "enum" not in get_field(services, "compliance-api", "/check", "post", "use_case")


@pytest.mark.parametrize("call", [
    lambda s: s["input-api"].post("/input", data={"use_case_id": "NOPE"}, files={"file": ("d.ttl", b"", "text/turtle")}),
    lambda s: s["input-api"].patch("/use-cases/NOPE/laws", data={"law": "GDPR"}),
    lambda s: s["compliance-api"].post("/check", data={"use_case": "NOPE", "law": "GDPR", "article": 30}),
    lambda s: s["compliance-api"].get("/use-cases/NOPE/assessments"),
    lambda s: s["compliance-api"].get("/use-cases/NOPE/laws"),
    lambda s: s["status-api"].get("/status", params={"use_case_id": "NOPE"}),
], ids=["input", "patch-laws", "check", "assessments", "laws", "status"])
def test_unknown_use_case_is_404(services, call):
    """Unknown use case is 404."""
    create(services, "TRIAGE")
    r = call(services)
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Use case not found"


@pytest.mark.parametrize("service,path,method,name", DROPDOWNS, ids=[f"{d[0]} {d[2]} {d[1]}" for d in DROPDOWNS])
def test_use_case_dropdown_says_to_reload(services, service, path, method, name):
    create(services, "UC1")
    assert "Reload this page" in get_field(services, service, path, method, name)["description"]
