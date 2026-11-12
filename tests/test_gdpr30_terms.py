"""GDPR Art. 30 accepts DPV 2.3 terms and the older names, with the same results."""
from pathlib import Path

from test_examples import run

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "previous" / "gdpr30_example.ttl"

# DPV 2.3 term -> older name still accepted
OLD_NAMES = {
    "dpv:hasJointDataControllers ": "dpv:hasJointDataController ",
    "a dpv:JointDataControllers ;": "a dpv:JointDataController ;",
}


def results(body):
    """Return a check's findings in a comparable, sorted form."""
    return sorted((tuple(f["requirement_ids"]), f["obligation"], f["focus_node"]) for f in body["findings"])


def test_old_and_new_terms_give_the_same_results(services, tmp_path):
    """Old and new terms give the same results."""
    new_terms = EXAMPLE.read_text()
    old_terms = new_terms
    for new, old in OLD_NAMES.items():
        assert new in new_terms
        old_terms = old_terms.replace(new, old)
    old_file = tmp_path / "old_terms.ttl"
    old_file.write_text(old_terms)

    new_body = run(services, "GDPR", 30, EXAMPLE)
    services["input-api"].post("/use-cases", data={"use_case_id": "OLD", "law": "GDPR", "label": "x"})
    services["input-api"].post("/input", data={"use_case_id": "OLD"},
                               files={"file": ("d.ttl", old_file.read_bytes(), "text/turtle")})
    old_body = services["compliance-api"].post("/check", data={"use_case": "OLD", "law": "GDPR", "article": 30}).json()
    assert results(old_body) == results(new_body)
    assert {r["id"]: r["status"] for r in old_body["requirements"]} == {r["id"]: r["status"] for r in new_body["requirements"]}


def test_joint_controller_found_with_dpv_2_3_terms(services):
    """Joint controller found with DPV 2.3 terms."""
    body = run(services, "GDPR", 30, EXAMPLE)
    status = {r["id"]: r["status"] for r in body["requirements"]}
    assert status["A30-1-11"] == "passed"   # dpv:hasJointDataControllers
    assert status["A30-1-12"] == "passed"   # dpv:JointDataControllers has a name


def test_recipient_checks_are_warnings(services):
    """Recipient checks are warnings."""
    body = run(services, "GDPR", 30, EXAMPLE)
    obligation = {i: f["obligation"] for f in body["findings"] for i in f["requirement_ids"]}
    assert obligation == {"A30-1-19": "recommended", "A30-1-20": "recommended", "A30-1-22": "recommended",
                          "A30-1-34": "mandatory", "G_Base-1": "mandatory"}


def test_alternative_path_is_reported_as_its_properties(services):
    rdf = b"""
@prefix dpv: <https://w3id.org/dpv#> .
@prefix ex: <http://example.com/> .
ex:P a dpv:Process .
"""
    services["input-api"].post("/use-cases", data={"use_case_id": "UC1", "law": "GDPR", "label": "x"})
    services["input-api"].post("/input", data={"use_case_id": "UC1"}, files={"file": ("d.ttl", rdf, "text/turtle")})
    body = services["compliance-api"].post("/check", data={"use_case": "UC1", "law": "GDPR", "article": 30}).json()
    joint = next(f for f in body["findings"] if "A30-1-11" in f["requirement_ids"])
    assert joint["property"] == "https://w3id.org/dpv#hasJointDataControllers | https://w3id.org/dpv#hasJointDataController"
