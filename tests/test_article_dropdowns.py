"""/docs offers the supported article numbers as dropdowns; mismatched articles are rejected."""
from conftest import load_service

ALL_ARTICLES = [10, 11, 20, 21, 30, 32]
BY_LAW = "GDPR: 30, 32 · NIS2: 20, 21 · EU_AI_ACT: 10, 11"


def check_article_field(services):
    """Return the article field schema of POST /check from /openapi.json."""
    spec = services["compliance-api"].get("/openapi.json").json()
    ref = spec["paths"]["/check"]["post"]["requestBody"]["content"]["application/x-www-form-urlencoded"]["schema"]["$ref"]
    return spec["components"]["schemas"][ref.rsplit("/", 1)[-1]]["properties"]["article"]


def status_article_field(services):
    """Return the article parameter schema of GET /status from /openapi.json."""
    spec = services["status-api"].get("/openapi.json").json()
    return next(p for p in spec["paths"]["/status"]["get"]["parameters"] if p["name"] == "article")["schema"]


def test_check_article_is_a_dropdown(services):
    """POST /check offers the supported articles as a dropdown."""
    field = check_article_field(services)
    assert field["enum"] == ALL_ARTICLES and field["type"] == "integer"
    assert field["description"] == BY_LAW


def test_status_article_is_a_dropdown(services):
    """GET /status offers the supported articles as a dropdown."""
    field = status_article_field(services)
    assert field["enum"] == ALL_ARTICLES and field["type"] == "integer"
    assert field["description"] == BY_LAW


def test_status_api_articles_match_compliance_api():
    """The Status API's article list matches the Compliance API's ASSESSMENTS."""
    compliance = load_service("compliance-api")
    status = load_service("status-api")
    from_shapes = {}
    for law, article in compliance.ASSESSMENTS:
        from_shapes.setdefault(law, set()).add(article)
    assert {law: set(articles) for law, articles in status.ARTICLES.items()} == from_shapes


def test_status_rejects_article_of_another_law(services):
    """GET /status rejects an article that belongs to another law."""
    services["input-api"].post("/use-cases", data={"use_case_id": "TRIAGE", "law": "GDPR", "label": "x"})
    r = services["status-api"].get("/status", params={"use_case_id": "TRIAGE", "law": "GDPR", "article": 10})
    assert r.status_code == 400
    assert "Supported articles: [30, 32]" in r.json()["detail"]


def test_check_rejects_article_of_another_law(services):
    """POST /check rejects an article that belongs to another law."""
    services["input-api"].post("/use-cases", data={"use_case_id": "TRIAGE", "law": "GDPR", "label": "x"})
    services["input-api"].post("/input", data={"use_case_id": "TRIAGE"},
                               files={"file": ("d.ttl", b"<http://e/x> <http://e/p> 1 .", "text/turtle")})
    r = services["compliance-api"].post("/check", data={"use_case": "TRIAGE", "law": "GDPR", "article": 10})
    assert r.status_code == 400
    assert "30" in r.json()["detail"] and "32" in r.json()["detail"]


def test_check_per_law_lists_only_its_articles(services):
    spec = services["compliance-api"].get("/openapi.json").json()
    for law, articles in {"GDPR": [30, 32], "NIS2": [20, 21], "EU_AI_ACT": [10, 11]}.items():
        body = spec["paths"][f"/check/{law}"]["post"]["requestBody"]["content"]
        ref = body["application/x-www-form-urlencoded"]["schema"]["$ref"]
        field = spec["components"]["schemas"][ref.rsplit("/", 1)[-1]]["properties"]["article"]
        assert field["enum"] == articles


def test_check_per_law_runs_the_check(services):
    services["input-api"].post("/use-cases", data={"use_case_id": "TRIAGE", "law": "GDPR", "label": "x"})
    services["input-api"].post("/input", data={"use_case_id": "TRIAGE"},
                               files={"file": ("d.ttl", b"<http://e/x> <http://e/p> 1 .", "text/turtle")})
    r = services["compliance-api"].post("/check/GDPR", data={"use_case": "TRIAGE", "article": 32})
    assert r.status_code == 200 and r.json()["law"] == "GDPR" and r.json()["article"] == 32
    r = services["compliance-api"].post("/check/GDPR", data={"use_case": "TRIAGE", "article": 10})
    assert r.status_code == 400
