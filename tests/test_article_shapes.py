"""Each article has its own shapes: compliant data passes, gaps fail with that article's requirement ids."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHAPES = ROOT / "compliance-api"

PREFIXES = """
@prefix dpv: <https://w3id.org/dpv#> .
@prefix ex: <http://example.com/> .
@prefix recitals: <http://example.org/recitals/> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix ai: <https://w3id.org/dpv/ai#> .
@prefix eu-aiact: <https://w3id.org/dpv/legal/eu/aiact#> .
@prefix tech: <https://w3id.org/dpv/tech#> .
@prefix schema: <https://schema.org/> .
"""

GDPR32_OK = PREFIXES + """
ex:Activity a dpv:Process ;
    dpv:hasPersonalData ex:Health ;
    dpv:hasRiskLevel ex:Medium ;
    dpv:hasTechnicalMeasure ex:Aes, dpv:AccessControlMethod, ex:Backups ;
    dpv:hasOrganisationalMeasure ex:PenTest, dpv:StaffTraining, dpv:RiskAssessment .
ex:Health a dpv:SpecialCategoryPersonalData .
ex:Aes a dpv:Encryption .
ex:Backups a dpv:DataBackupProtocols .
ex:PenTest a dpv:ReviewProcedure .
"""

GDPR32_GAPS = PREFIXES + """
ex:Activity a dpv:Process ;
    dpv:hasPersonalData ex:Health ;
    dpv:hasTechnicalMeasure ex:Firewall .
ex:Health a dpv:SpecialCategoryPersonalData .
ex:Firewall a dpv:TechnicalMeasure .
"""

NIS2_20_OK = PREFIXES + """
ex:Acme a recitals:EssentialEntity ;
    recitals:hasManagementBody ex:Board ;
    dpv:hasOrganisationalMeasure ex:RiskPolicy, dpv:CybersecurityTraining .
ex:Board a recitals:ManagementBody ;
    dpv:hasOrganisationalMeasure dpv:CybersecurityTraining .
ex:RiskPolicy a recitals:CybersecurityRiskManagementMeasure ;
    recitals:approvedBy ex:Board ;
    recitals:implementationOverseenBy ex:Board .
"""

NIS2_20_GAPS = PREFIXES + """
ex:Acme a recitals:ImportantEntity ;
    recitals:hasManagementBody ex:Board ;
    dpv:hasOrganisationalMeasure ex:RiskPolicy .
ex:Board a recitals:ManagementBody .
ex:RiskPolicy a recitals:CybersecurityRiskManagementMeasure ;
    recitals:approvedBy ex:Board .
"""

# Art. 21 has many required measures; reuse the example files.
NIS2_21_OK = (ROOT / "examples" / "nis2_21_compliant.ttl").read_text()
NIS2_21_GAPS = (ROOT / "examples" / "previous" / "nis2_21_noncompliant.ttl").read_text()

DATASET = """
    recitals:hasDesignChoice "x" ; dpv:hasProcessing ai:DataCollection , ai:DataLabelling ;
    dpv:hasDataSource ex:Registry ; recitals:hasAssumption "x" ;
    dpv:hasAssessment dpv:DataSuitabilityAssessment , ai:BiasAssessment ;
    dpv:hasOrganisationalMeasure ai:BiasMitigation ;
    recitals:hasDataGapAnalysis "x" ; recitals:hasStatisticalProperties "x"
"""

AI10_OK = PREFIXES + f"""
ex:Triage a eu-aiact:HighRiskAISystem ;
    ai:hasModel [ a ai:TrainedModel ] ;
    dpv:hasGeographicCoverage ex:Ireland ;
    ai:hasTrainingData ex:Train ;
    ai:hasValidationData ex:Val ;
    ai:hasTestingData ex:Test .
ex:Train {DATASET} ;
    dpv:hasPersonalData ex:Health ; dpv:hasPurpose ex:Care ;
    dpv:hasTechnicalMeasure dpv:Pseudonymisation, dpv:AccessControlMethod ;
    dpv:hasStorageCondition ex:DeleteAfterBiasFix ;
    dpv:hasJustification "bias detection by ethnicity" .
ex:Val {DATASET} .
ex:Test {DATASET} .
ex:Health a dpv:SpecialCategoryPersonalData .
"""

AI10_GAPS = PREFIXES + """
ex:Triage a eu-aiact:HighRiskAISystem ;
    ai:hasModel [ a ai:TrainedModel ] ;
    ai:hasTrainingData ex:Train .
ex:Train dpv:hasPersonalData ex:Health .
ex:Health a dpv:SpecialCategoryPersonalData .
"""

AI11_OK = PREFIXES + """
ex:Triage a eu-aiact:HighRiskAISystem ;
    tech:hasProvider ex:Acme ;
    dpv:hasPurpose ex:Triage ;
    schema:version "2.1" ;
    tech:hasMarketAvailabilityStatus [ a eu-aiact:PlacedOnMarket ; dct:date "2026-08-01"^^xsd:date ] ;
    tech:hasDocumentation ex:Doc .
ex:Doc a eu-aiact:TechnicalDocumentation ;
    dct:created "2026-07-01T09:00:00Z"^^xsd:dateTime ;
    schema:version "2.1" ;
    dct:hasPart eu-aiact:InstructionForUse , eu-aiact:SystemArchitectureDescription ,
        eu-aiact:ProviderHumanOversightMeasure , eu-aiact:AISystemPerformance ,
        eu-aiact:RiskManagementSystem , eu-aiact:ChangeDescription ,
        eu-aiact:EUDeclarationOfConformity , eu-aiact:PostMarketMonitoringPlan ;
    dct:conformsTo ex:ISO42001 .
"""

AI11_GAPS = PREFIXES + """
ex:Triage a eu-aiact:HighRiskAISystem ;
    tech:hasProvider ex:Acme ;
    dpv:hasPurpose ex:Triage ;
    schema:version "2.2" ;
    tech:hasMarketAvailabilityStatus [ a eu-aiact:PlacedOnMarket ; dct:date "2026-08-01"^^xsd:date ] ;
    tech:hasDocumentation ex:Doc .
ex:Doc a eu-aiact:TechnicalDocumentation ;
    dct:created "2026-09-01"^^xsd:date ;
    schema:version "2.1" ;
    dct:hasPart eu-aiact:InstructionForUse .
"""

UNRELATED = PREFIXES + "ex:Thing a ex:Widget .\n"

CASES = [
    # law, article, compliant data, gappy data, ids that must be reported for the gaps
    ("GDPR", 32, GDPR32_OK, GDPR32_GAPS,
     {"A32-1-2", "A32-2", "A32-1-a", "A32-1-b", "A32-1-c", "A32-1-d", "A32-4"}),
    ("NIS2", 20, NIS2_20_OK, NIS2_20_GAPS, {"N20-1-2", "N20-2-1", "N20-2-2"}),
    ("NIS2", 21, NIS2_21_OK, NIS2_21_GAPS, {"N21-2-b", "N21-2-c-2", "N21-2-d", "N21-2-e", "N21-2-f", "N21-2-g-1", "N21-2-g-2", "N21-2-h-1", "N21-2-h-2", "N21-2-i-1", "N21-2-i-3", "N21-2-j-1", "N21-2-j-2", "N21-2-j-3", "N21-3-1", "N21-3-2"}),
    ("EU_AI_ACT", 10, AI10_OK, AI10_GAPS,
     {"AIA10-1-2", "AIA10-1-3", "AIA10-2-a", "AIA10-2-b", "AIA10-2-h", "AIA10-4",
      "AIA10-5-b", "AIA10-5-c", "AIA10-5-e", "AIA10-5-f"}),
    ("EU_AI_ACT", 11, AI11_OK, AI11_GAPS,
     {"AIA11-1-2", "AIA11-1-3", "AIA11-AIV-2", "AIA11-AIV-5", "AIA11-AIV-7", "AIA11-AIV-9"}),
]


def check(services, law, article, rdf):
    """Create UC1 for a law, upload the data and run the article check."""
    r = services["input-api"].post("/use-cases", data={"use_case_id": "UC1", "law": law, "label": "t"})
    assert r.status_code == 201, r.text
    r = services["input-api"].post(
        "/input", data={"use_case_id": "UC1"}, files={"file": ("d.ttl", rdf.encode(), "text/turtle")}
    )
    assert r.status_code == 201, r.text
    r = services["compliance-api"].post("/check", data={"use_case": "UC1", "law": law, "article": article})
    assert r.status_code == 200, r.text
    return r.json()


def reported_ids(body):
    """Return every requirement id reported in a check's findings."""
    return {i for f in body["findings"] for i in f["requirement_ids"]}


def test_shape_files_are_distinct():
    """Each article has its own shapes file (they used to be copies)."""
    files = ["shapes_gdpr30.ttl", "shapes_gdpr32.ttl", "shapes_nis2_20.ttl",
             "shapes_nis2_21.ttl", "shapes_eu_act_10.ttl", "shapes_eu_act_11.ttl"]
    contents = [(SHAPES / f).read_bytes() for f in files]
    assert len(set(contents)) == len(files)


@pytest.mark.parametrize("law,article,ok,_gaps,_ids", CASES, ids=[f"{c[0]}-{c[1]}" for c in CASES])
def test_compliant_data_passes(services, law, article, ok, _gaps, _ids):
    """Compliant data passes."""
    body = check(services, law, article, ok)
    assert body["status"] == "passed", body["findings"]


@pytest.mark.parametrize("law,article,_ok,gaps,ids", CASES, ids=[f"{c[0]}-{c[1]}" for c in CASES])
def test_gaps_are_reported_with_article_ids(services, law, article, _ok, gaps, ids):
    """Gaps are reported with article ids."""
    body = check(services, law, article, gaps)
    assert body["status"] == "failed"
    assert all(f["requirement_ids"] for f in body["findings"]), body["findings"]
    missing = ids - reported_ids(body)
    assert not missing, (missing, body["findings"])


@pytest.mark.parametrize("law,article", [(c[0], c[1]) for c in CASES], ids=[f"{c[0]}-{c[1]}" for c in CASES])
def test_data_without_anything_in_scope_fails(services, law, article):
    """Data with nothing the article applies to fails instead of passing."""
    body = check(services, law, article, UNRELATED)
    assert body["status"] == "failed"
    assert any(i.endswith("-0") for i in reported_ids(body)), body["findings"]


def test_art30_rules_no_longer_run_for_other_articles(services):
    # An incomplete processing activity fails Art. 30 but has nothing to do with NIS2 Art. 20.
    """Art. 30 rules no longer run for other articles."""
    body = check(services, "NIS2", 20, PREFIXES + "ex:A a dpv:Process .\n")
    assert not any(i.startswith("A30") for i in reported_ids(body)), body["findings"]


def test_severity_distinguishes_mandatory_from_as_appropriate(services):
    """Mandatory requirements are Violations; "as appropriate" ones are Warnings."""
    body = check(services, "GDPR", 32, GDPR32_GAPS)
    obligation = {i: f["obligation"] for f in body["findings"] for i in f["requirement_ids"]}
    assert obligation["A32-2"] == "mandatory"
    assert obligation["A32-1-a"] == "mandatory"  # special category data without encryption
    assert obligation["A32-1-b"] == "recommended"
    assert obligation["A32-4"] == "recommended"
