"""The example files in examples/ give the results their headers describe."""
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

CASES = [
    # file prefix, law, article, ids the non-compliant file must report
    # (each non-compliant file is its compliant file with one change)
    ("gdpr30", "GDPR", 30, {"A30-1-24"}),
    ("gdpr32", "GDPR", 32, {"A32-1-a"}),
    ("nis2_20", "NIS2", 20, {"N20-2-1"}),
    ("nis2_21", "NIS2", 21, {"N21-2-b"}),
    ("eu_ai_act_10", "EU_AI_ACT", 10, {"AIA10-2-f"}),
    ("eu_ai_act_11", "EU_AI_ACT", 11, {"AIA11-1-3"}),
]
IDS = [c[0] for c in CASES]

# The earlier non-compliant files in examples/previous/ have many gaps
# each, so they keep most failing checks covered.
PREVIOUS = [
    ("gdpr32", "GDPR", 32, {"A32-1-2", "A32-2", "A32-1-a", "A32-1-b", "A32-1-c", "A32-1-d", "A32-4"}),
    ("nis2_20", "NIS2", 20, {"N20-1-1", "N20-1-2", "N20-2-1", "N20-2-2"}),
    ("nis2_21", "NIS2", 21,
     {"N21-2-b", "N21-2-c-2", "N21-2-d", "N21-2-e", "N21-2-f", "N21-2-g-1", "N21-2-g-2", "N21-2-h-1", "N21-2-h-2", "N21-2-i-1", "N21-2-i-3", "N21-2-j-1", "N21-2-j-2", "N21-2-j-3", "N21-3-1", "N21-3-2"}),
    ("eu_ai_act_10", "EU_AI_ACT", 10,
     {"AIA10-1-2", "AIA10-1-3", "AIA10-2-a", "AIA10-2-b", "AIA10-2-c", "AIA10-2-d", "AIA10-2-e",
      "AIA10-2-g", "AIA10-2-h", "AIA10-3", "AIA10-4", "AIA10-5-b", "AIA10-5-c", "AIA10-5-e", "AIA10-5-f"}),
    ("eu_ai_act_11", "EU_AI_ACT", 11,
     {"AIA11-1-2", "AIA11-1-3", "AIA11-AIV-2", "AIA11-AIV-3", "AIA11-AIV-4", "AIA11-AIV-5",
      "AIA11-AIV-6", "AIA11-AIV-7", "AIA11-AIV-8", "AIA11-AIV-9"}),
]


def run(services, law, article, path):
    """Create a use case, upload an example file and run its article check."""
    r = services["input-api"].post("/use-cases", data={"use_case_id": "UC1", "law": law, "label": path.stem})
    assert r.status_code == 201, r.text
    r = services["input-api"].post(
        "/input", data={"use_case_id": "UC1"}, files={"file": (path.name, path.read_bytes(), "text/turtle")}
    )
    assert r.status_code == 201, r.text
    r = services["compliance-api"].post("/check", data={"use_case": "UC1", "law": law, "article": article})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("name,law,article,_ids", CASES, ids=IDS)
def test_compliant_example_passes(services, name, law, article, _ids):
    """Compliant example passes."""
    body = run(services, law, article, EXAMPLES / f"{name}_compliant.ttl")
    assert body["status"] == "passed", body["findings"]


@pytest.mark.parametrize("name,law,article,ids", CASES, ids=IDS)
def test_noncompliant_example_reports_expected_findings(services, name, law, article, ids):
    """Noncompliant example reports expected findings."""
    body = run(services, law, article, EXAMPLES / f"{name}_noncompliant.ttl")
    assert body["status"] == "failed"
    reported = {i for f in body["findings"] for i in f["requirement_ids"]}
    assert reported == ids, (reported - ids, ids - reported)


@pytest.mark.parametrize("name,law,article,ids", PREVIOUS, ids=[c[0] for c in PREVIOUS])
def test_previous_noncompliant_example_reports_expected_findings(services, name, law, article, ids):
    body = run(services, law, article, EXAMPLES / "previous" / f"{name}_noncompliant.ttl")
    assert body["status"] == "failed"
    reported = {i for f in body["findings"] for i in f["requirement_ids"]}
    assert reported == ids, (reported - ids, ids - reported)
