
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Tuple
import re
import uuid

import requests

from fastapi import FastAPI, HTTPException
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD
from pyshacl import validate
from fastapi import Form

# ============================================================
# FastAPI
# ============================================================

app = FastAPI(
    title="RECITALS Compliance API",
    description="RECITALS compliance validation using SHACL",
    version="1.0.0"
)


# ============================================================
# Namespaces
# ============================================================

RECITALS = Namespace(
    "http://example.org/recitals/"
)

SH = Namespace(
    "http://www.w3.org/ns/shacl#"
)

DCT = Namespace(
    "http://purl.org/dc/terms/"
)

XSD_NS = XSD


# ============================================================
# Fuseki configuration
# ============================================================

FUSEKI_QUERY_URL = (
    "http://fuseki:3030/dataset/query"
)

FUSEKI_DATA_URL = (
    "http://fuseki:3030/dataset/data"
)

FUSEKI_USER = "admin"
FUSEKI_PASSWORD = "admin"


# ============================================================
# Named graph for compliance assessments
# ============================================================

RESULTS_GRAPH = (
    "http://example.org/assessments"
)


# ============================================================
# SHACL assessment definitions
# ============================================================

ASSESSMENTS = {
    ("GDPR", 30): "shapes_gdpr30.ttl",
    ("GDPR", 32): "shapes_gdpr32.ttl",

    ("EU_AI_ACT", 10): "shapes_eu_ai_act_10.ttl",
    ("EU_AI_ACT", 11): "shapes_eu_ai_act_11.ttl",

    ("NIS2", 20): "shapes_nis2_20.ttl",
    ("NIS2", 22): "shapes_nis2_22.ttl",
}


# ============================================================
# Enum definitions
# ============================================================

class Law(str, Enum):
    GDPR = "GDPR"
    NIS2 = "NIS2"
    EU_AI_ACT = "EU_AI_ACT"


class Article(int, Enum):

    article_30 = 30
    article_32 = 32



class UseCase(str, Enum):
    UC1 = "UC1"
    UC2 = "UC2"
    UC3 = "UC3"
# ============================================================
# Helper functions
# ============================================================

def use_case_uri(use_case_id: str) -> URIRef:

    """
    Return the URI used by the Input API for a use case.

    Example:

    UC1
    ->
    http://example.org/recitals/UC1
    """

    return URIRef(
        f"http://example.org/recitals/{use_case_id}"
    )


def validate_use_case_id(
    use_case_id: str
) -> None:

    """
    Validate the use case identifier.
    """

    if not re.fullmatch(
        r"[A-Za-z0-9_-]{1,80}",
        use_case_id
    ):

        raise HTTPException(
            status_code=422,
            detail=(
                "use_case_id may contain only "
                "letters, numbers, underscores, "
                "and hyphens"
            )
        )


# ============================================================
# Fuseki query helper
# ============================================================

def query_fuseki(
    query: str
) -> Dict:

    """
    Execute a SPARQL SELECT query against Fuseki.
    """

    try:

        response = requests.post(

            FUSEKI_QUERY_URL,

            data=query,

            headers={
                "Content-Type":
                "application/sparql-query",
                "Accept":
                "application/sparql-results+json"
            },

            auth=(
                FUSEKI_USER,
                FUSEKI_PASSWORD
            ),

            timeout=15
        )

    except requests.RequestException:

        raise HTTPException(
            status_code=503,
            detail="Triple store unavailable"
        )

    if response.status_code != 200:

        raise HTTPException(
            status_code=502,
            detail=(
                "Triple store query failed: "
                + response.text
            )
        )

    try:

        return response.json()

    except ValueError:

        raise HTTPException(
            status_code=502,
            detail="Invalid response from triple store"
        )


# ============================================================
# Get existing use cases
# ============================================================

def get_existing_use_cases() -> List[Dict]:

    """
    Retrieve use cases already stored in the
    triplestore.

    This is deliberately based on the RDF representation
    created by the Input API.

    Example:

    recitals:UC1
        a recitals:UseCase ;
        rdfs:label "Employee Recruitment" ;
        recitals:hasApplicableLaw recitals:GDPR .
    """

    query = f"""

    PREFIX recitals: <{RECITALS}>
    PREFIX rdfs: <{RDFS}>

    SELECT ?uc ?label ?law

    WHERE {{

        ?uc a recitals:UseCase ;
            rdfs:label ?label .

        OPTIONAL {{

            ?uc recitals:hasApplicableLaw ?law .

        }}

    }}

    ORDER BY ?uc

    """

    results = query_fuseki(query)

    use_cases = {}

    for row in results[
        "results"
    ][
        "bindings"
    ]:

        uri = row["uc"]["value"]

        use_case_id = uri.rsplit(
            "/",
            1
        )[-1]

        if use_case_id not in use_cases:

            use_cases[
                use_case_id
            ] = {

                "use_case_id":
                    use_case_id,

                "label":
                    row["label"]["value"],

                "applicable_laws":
                    [],

                "uri":
                    uri

            }

        if "law" in row:

            law_uri = row[
                "law"
            ][
                "value"
            ]

            law = law_uri.rsplit(
                "/",
                1
            )[-1]

            if law not in use_cases[
                use_case_id
            ][
                "applicable_laws"
            ]:

                use_cases[
                    use_case_id
                ][
                    "applicable_laws"
                ].append(law)

    return list(
        use_cases.values()
    )


# ============================================================
# Check whether use case exists
# ============================================================

def use_case_exists(
    use_case_id: str
) -> bool:

    """

    Check whether the use case exists in the
    triplestore.

    """

    query = f"""

    PREFIX recitals: <{RECITALS}>

    ASK {{

        <{use_case_uri(use_case_id)}>
            a recitals:UseCase .

    }}

    """

    try:

        response = requests.post(

            FUSEKI_QUERY_URL,

            data=query,

            headers={
                "Content-Type":
                "application/sparql-query",
                "Accept":
                "application/sparql-results+json"
            },

            auth=(
                FUSEKI_USER,
                FUSEKI_PASSWORD
            ),

            timeout=15
        )

    except requests.RequestException:

        raise HTTPException(
            status_code=503,
            detail="Triple store unavailable"
        )

    if response.status_code != 200:

        raise HTTPException(
            status_code=502,
            detail="Failed to check use case"
        )

    try:

        return bool(
            response.json().get(
                "boolean",
                False
            )
        )

    except ValueError:

        raise HTTPException(
            status_code=502,
            detail="Invalid response from triple store"
        )


# ============================================================
# Fetch use case RDF
# ============================================================

def fetch_graph(
    use_case_id: str
) -> Graph:

    """
    Fetch the RDF data belonging to a use case.

    The Input API stores use case data using the
    use-case URI.

    This query retrieves all triples where the use case
    is the subject.

    """

    resource = use_case_uri(
        use_case_id
    )

    query = f"""

    CONSTRUCT {{

        <{resource}> ?p ?o .

    }}

    WHERE {{

        <{resource}> ?p ?o .

    }}

    """

    try:

        response = requests.post(

            FUSEKI_QUERY_URL,

            data=query,

            headers={
                "Content-Type":
                "application/sparql-query",
                "Accept":
                "text/turtle"
            },

            auth=(
                FUSEKI_USER,
                FUSEKI_PASSWORD
            ),

            timeout=15
        )

    except requests.RequestException:

        raise HTTPException(
            status_code=503,
            detail="Triple store unavailable"
        )

    if response.status_code != 200:

        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to fetch use-case "
                "data from Fuseki"
            )
        )

    graph = Graph()

    if response.text.strip():

        graph.parse(
            data=response.text,
            format="turtle"
        )

    return graph


# ============================================================
# Extract SHACL findings
# ============================================================

def findings_from(
    report: Graph
) -> List[Dict[str, object]]:

    findings = []

    for result in report.subjects(
        RDF.type,
        SH.ValidationResult
    ):

        source = report.value(
            result,
            SH.sourceShape
        )

        requirement_ids = []

        if source is not None:

            for value in report.objects(
                source,
                DCT.identifier
            ):

                requirement_ids.append(
                    str(value)
                )

        message = report.value(
            result,
            SH.resultMessage
        )

        severity = report.value(
            result,
            SH.resultSeverity
        )

        focus_node = report.value(
            result,
            SH.focusNode
        )

        result_path = report.value(
            result,
            SH.resultPath
        )

        if severity is not None:

            severity_value = str(
                severity
            ).rsplit(
                "#",
                1
            )[-1]

        else:

            severity_value = "Violation"

        findings.append({

            "requirement_ids":
                requirement_ids,

            "message":
                str(
                    message
                    or
                    "Validation failed"
                ),

            "severity":
                severity_value,

            "focus_node":
                str(
                    focus_node
                    or
                    ""
                ),

            "property":
                (
                    str(result_path)
                    if result_path
                    else None
                )

        })

    return findings


# ============================================================
# Store compliance assessment
# ============================================================

def store_result(
    use_case_id: str,
    law: Law,
    article: int,
    conforms: bool,
    findings: List[Dict[str, object]]
) -> Tuple[str, str]:

    assessment_id = str(uuid.uuid4())

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    assessment_uri = URIRef(
        f"{RECITALS}assessment_{assessment_id}"
    )

    report_uri = URIRef(
        f"{RECITALS}report_{assessment_id}"
    )

    use_case = use_case_uri(
        use_case_id
    )

    graph = Graph()

    graph.bind("recitals", RECITALS)
    graph.bind("sh", SH)
    graph.bind("dct", DCT)

    # ----------------------------------------------------
    # Assessment
    # ----------------------------------------------------

    graph.add((assessment_uri,
               RDF.type,
               RECITALS.ComplianceAssessment))

    graph.add((assessment_uri,
               RECITALS.assessmentId,
               Literal(assessment_id)))

    graph.add((assessment_uri,
               RECITALS.belongsToUseCase,
               use_case))

    graph.add((use_case,
               RECITALS.hasAssessment,
               assessment_uri))

    graph.add((assessment_uri,
               RECITALS.assesses,
               URIRef(f"{RECITALS}{law.value}Article{article}")))

    graph.add((assessment_uri,
               RECITALS.law,
               RECITALS[law.value]))

    graph.add((assessment_uri,
               RECITALS.article,
               Literal(article)))

    graph.add((assessment_uri,
               RECITALS.assessmentStatus,
               Literal(
                   "passed"
                   if conforms
                   else "failed"
               )))

    graph.add((assessment_uri,
               DCT.created,
               Literal(
                   timestamp,
                   datatype=XSD.dateTime
               )))

    # ----------------------------------------------------
    # Validation Report
    # ----------------------------------------------------

    graph.add((report_uri,
               RDF.type,
               RECITALS.ValidationReport))

    graph.add((report_uri,
               SH.conforms,
               Literal(
                   conforms,
                   datatype=XSD.boolean
               )))

    graph.add((assessment_uri,
               RECITALS.hasReport,
               report_uri))

    # ----------------------------------------------------
    # Findings
    # ----------------------------------------------------

    for finding in findings:

        finding_uri = URIRef(
            f"{report_uri}/finding/{uuid.uuid4()}"
        )

        graph.add((report_uri,
                   RECITALS.hasFinding,
                   finding_uri))

        graph.add((finding_uri,
                   RDF.type,
                   SH.ValidationResult))

        graph.add((finding_uri,
                   RECITALS.message,
                   Literal(finding["message"])))

        graph.add((finding_uri,
                   RECITALS.severity,
                   Literal(finding["severity"])))

        graph.add((finding_uri,
                   RECITALS.focusNode,
                   Literal(finding["focus_node"])))

        if finding.get("property"):

            graph.add((finding_uri,
                       RECITALS.property,
                       Literal(finding["property"])))

        for req in finding["requirement_ids"]:

            graph.add((finding_uri,
                       RECITALS.requirementId,
                       Literal(req)))

    # ----------------------------------------------------
    # Store graph
    # ----------------------------------------------------

    response = requests.post(

        FUSEKI_DATA_URL,

        # params={
        #     "graph": RESULTS_GRAPH
        # },

        data=graph.serialize(
            format="turtle"
        ),

        headers={
            "Content-Type":
            "text/turtle"
        },

        auth=(
            FUSEKI_USER,
            FUSEKI_PASSWORD
        ),

        timeout=15
    )

    if response.status_code not in (
        200,
        201,
        204
    ):

        raise HTTPException(
            status_code=502,
            detail="Failed to store assessment."
        )

    return assessment_id, timestamp

# ============================================================
# GET existing use cases
# ============================================================

@app.get(
    "/use-cases"
)
def list_use_cases():

    """
    Return existing use cases from the triplestore.

    These can be used to populate the user interface
    dropdown.

    """

    return get_existing_use_cases()


# ============================================================
# GET assessments for a use case
# ============================================================

@app.get(
    "/use-cases/{use_case_id}/assessments"
)
def list_assessments(
    use_case_id: str
):

    """
    Return all compliance assessments belonging
    to one use case.
    """

    validate_use_case_id(
        use_case_id
    )

    if not use_case_exists(
        use_case_id
    ):

        raise HTTPException(
            status_code=404,
            detail="Use case not found"
        )

    resource = use_case_uri(use_case_id)

    query = f"""
    PREFIX recitals: <{RECITALS}>

    SELECT *
    WHERE {{

        ?assessment
            a recitals:ComplianceAssessment ;
            recitals:belongsToUseCase <{resource}> .

        OPTIONAL {{
            ?assessment recitals:assesses ?requirement .
        }}

        OPTIONAL {{
            ?assessment recitals:law ?law .
        }}

        OPTIONAL {{
            ?assessment recitals:article ?article .
        }}

        OPTIONAL {{
            ?assessment recitals:assessmentStatus ?status .
        }}

        OPTIONAL {{
            ?assessment recitals:conforms ?conforms .
        }}

        OPTIONAL {{
            ?assessment recitals:validationTimestamp ?timestamp .
        }}

    }}
    ORDER BY DESC(?timestamp)
    """

    results = query_fuseki(
        query
    )

    assessments = []

    for row in results[
        "results"
    ][
        "bindings"
    ]:

        requirement = row[
            "requirement"
        ][
            "value"
        ]

        requirement_name = requirement.rsplit(
            "/",
            1
        )[-1]

        assessments.append({

            "assessment_id":
                row[
                    "assessment"
                ][
                    "value"
                ].rsplit(
                    "_",
                    1
                )[-1],

            "assessment_uri":
                row[
                    "assessment"
                ][
                    "value"
                ],

            "use_case_id":
                use_case_id,

            "law": row["law"]["value"] if "law" in row else None,

            "article": int(row["article"]["value"]) if "article" in row else None,

            "requirement":
                requirement_name,

            "status": row["status"]["value"] if "status" in row else None,

            "conforms":
                row["conforms"]["value"].lower() == "true"
                if "conforms" in row
                else None,

            "timestamp":
                row["timestamp"]["value"]
                if "timestamp" in row
                else None,

        })

    return assessments


# ============================================================
# GET one assessment
# ============================================================

@app.get(
    "/assessments/{assessment_id}"
)
def get_assessment(
    assessment_id: str
):

    """
    Retrieve one assessment and its findings.
    """

    query = f"""
    PREFIX recitals: <{RECITALS}>
    PREFIX dct: <http://purl.org/dc/terms/>
    PREFIX sh: <http://www.w3.org/ns/shacl#>

    SELECT
        ?assessment
        ?use_case
        ?law
        ?article
        ?status
        ?created
        ?report
        ?conforms
        ?finding
        ?message
        ?severity
        ?focusNode
        ?requirementId

    WHERE {{

        ?assessment
            a recitals:ComplianceAssessment ;
            recitals:assessmentId "{assessment_id}" ;
            recitals:belongsToUseCase ?use_case ;
            recitals:law ?law ;
            recitals:article ?article ;
            recitals:assessmentStatus ?status ;
            dct:created ?created ;
            recitals:hasReport ?report .

        OPTIONAL {{
            ?report sh:conforms ?conforms .
        }}

        OPTIONAL {{

            ?report recitals:hasFinding ?finding .

            OPTIONAL {{
                ?finding recitals:message ?message .
            }}

            OPTIONAL {{
                ?finding recitals:severity ?severity .
            }}

            OPTIONAL {{
                ?finding recitals:focusNode ?focusNode .
            }}

            OPTIONAL {{
                ?finding recitals:requirementId ?requirementId .
            }}

        }}

    }}
    """

    results = query_fuseki(
        query
    )

    bindings = results[
        "results"
    ][
        "bindings"
    ]

    if not bindings:

        raise HTTPException(
            status_code=404,
            detail="Assessment not found"
        )

    first = bindings[0]

    assessment_uri = first[
        "assessment"
    ][
        "value"
    ]

    use_case_uri_value = first[
        "use_case"
    ][
        "value"
    ]

    use_case_id = use_case_uri_value.rsplit(
        "/",
        1
    )[-1]


    findings = []

    seen_findings = set()

    for row in bindings:

        if "finding" not in row:

            continue

        finding_uri = row[
            "finding"
        ][
            "value"
        ]

        if finding_uri in seen_findings:

            continue

        seen_findings.add(
            finding_uri
        )

        requirement_ids = []

        if "requirementId" in row:

            requirement_ids.append(
                row[
                    "requirementId"
                ][
                    "value"
                ]
            )

        findings.append({

            "message":
                row.get(
                    "message",
                    {}
                ).get(
                    "value",
                    ""
                ),

            "severity":
                row.get(
                    "severity",
                    {}
                ).get(
                    "value",
                    "Violation"
                ),

            "focus_node":
                row.get(
                    "focusNode",
                    {}
                ).get(
                    "value",
                    ""
                ),

            "requirement_ids":
                requirement_ids

        })

    return {

        "assessment_id":
            assessment_id,

        "assessment_uri":
            assessment_uri,

        "use_case_id":
            use_case_id,

        "law":
            first["law"]["value"].rsplit("/", 1)[-1]
            if "law" in first else None,

        "article":
            int(first["article"]["value"])
            if "article" in first else None,

        "status":
            first["status"]["value"]
            if "status" in first else None,

        "conforms":
            first["conforms"]["value"].lower() == "true"
            if "conforms" in first else None,

        "created":
            first["created"]["value"]
            if "created" in first else None,

        "findings":
            findings

    }

@app.get("/use-cases")
def get_use_cases():

    query = f"""
    PREFIX recitals: <{RECITALS}>
    PREFIX rdfs: <{RDFS}>

    SELECT ?uc ?label
    WHERE {{

        ?uc a recitals:UseCase ;
            rdfs:label ?label .

    }}

    ORDER BY ?label
    """

    results = query_fuseki(query)

    use_cases = []

    for row in results["results"]["bindings"]:

        uri = row["uc"]["value"]

        use_cases.append({

            "id": uri.rsplit("/", 1)[-1],

            "label": row["label"]["value"]

        })

    return use_cases

@app.get("/use-cases/{use_case_id}/laws")
def get_use_case_laws(
    use_case_id: str
):

    resource = use_case_uri(use_case_id)

    query = f"""
    PREFIX recitals: <{RECITALS}>

    SELECT ?law
    WHERE {{

        {resource.n3()} recitals:hasApplicableLaw ?law .

    }}
    """

    results = query_fuseki(query)

    laws = []

    for row in results["results"]["bindings"]:

        laws.append(

            row["law"]["value"].rsplit("/",1)[-1]

        )

    return laws
# ============================================================
# POST /check
# ============================================================

@app.post("/check")
def check(
    use_case: UseCase = Form(...),
    law: Law = Form(...),
    article: int = Form(...)
):
    """
    Run one article-level compliance assessment.
    """

    # --------------------------------------------------------
    # Resolve enum values
    # --------------------------------------------------------

    use_case_id = use_case.value

    # --------------------------------------------------------
    # Validate use case id
    # --------------------------------------------------------

    validate_use_case_id(use_case_id)

    # --------------------------------------------------------
    # Check use case exists
    # --------------------------------------------------------

    if not use_case_exists(use_case_id):
        raise HTTPException(
            status_code=404,
            detail="Use case not found"
        )

    # --------------------------------------------------------
    # Check selected law belongs to the use case
    # --------------------------------------------------------

    use_case_laws = get_use_case_laws(use_case_id)

    if law.value not in use_case_laws:
        raise HTTPException(
            status_code=400,
            detail=f"{law.value} is not applicable to {use_case_id}"
        )

    # --------------------------------------------------------
    # Check article belongs to the selected law
    # --------------------------------------------------------

    allowed_articles = get_articles_for_law(law)

    if article not in allowed_articles:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Article {article} is not available for "
                f"{law.value}. "
                f"Available articles: {allowed_articles}"
            )
        )

    # --------------------------------------------------------
    # Get SHACL shape
    # --------------------------------------------------------

    shape_file = ASSESSMENTS.get(
        (
            law.value,
            article
        )
    )

    if shape_file is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No assessment available for "
                f"{law.value} Article {article}"
            )
        )

    # --------------------------------------------------------
    # Fetch RDF graph
    # --------------------------------------------------------

    data_graph = fetch_graph(use_case_id)

    if len(data_graph) == 0:
        raise HTTPException(
            status_code=404,
            detail="Use case contains no RDF data"
        )

    # --------------------------------------------------------
    # Load SHACL graph
    # --------------------------------------------------------

    shapes = Graph()

    try:
        shapes.parse(
            shape_file,
            format="turtle"
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to load SHACL shapes: {exc}"
        )

    # --------------------------------------------------------
    # Execute validation
    # --------------------------------------------------------

    try:

        conforms, report, _ = validate(
            data_graph,
            shacl_graph=shapes,
            inference="rdfs",
            debug=False
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"SHACL validation failed: {exc}"
        )

    # --------------------------------------------------------
    # Extract findings
    # --------------------------------------------------------

    findings = findings_from(report)

    # --------------------------------------------------------
    # Store assessment
    # --------------------------------------------------------

    assessment_id, timestamp = store_result(
        use_case_id=use_case_id,
        law=law,
        article=article,
        conforms=conforms,
        findings=findings
    )

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {

        "assessment_id": assessment_id,

        "use_case_id": use_case_id,

        "law": law.value,

        "article": article,

        "requirement": f"{law.value}Article{article}",

        "status":
            "passed" if conforms else "failed",

        "conforms": conforms,

        "timestamp": timestamp,

        "findings": findings

    }

@app.get("/laws/{law}/articles")
def list_articles(law: Law):

    return {
        "law": law.value,
        "articles": get_articles_for_law(law)
    }

# ============================================================
# Legacy endpoint
# ============================================================

@app.post(
    "/validate"
)
def validate_legacy(
    service: str,
    compliance_type: str,
    version_id: str
):

    """
    Compatibility wrapper for the original endpoint.

    Examples:

    gdpr30 -> Article 30
    gdpr32 -> Article 32

    The new /check endpoint is preferred.
    """

    if compliance_type == "gdpr30":

        article = 30

    elif compliance_type == "gdpr32":

        article = 32

    else:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported compliance type"
            )
        )

    return check(
        version_id,
        Law.gdpr,
        article
    )

def get_articles_for_law(law: Law):
    return sorted(
        article
        for (law_name, article) in ASSESSMENTS.keys()
        if law_name == law.value
    )

@app.get(
    "/assessments/{assessment_id}/report"
)
def get_assessment_report(
    assessment_id: str
):

    query = f"""
    PREFIX recitals: <{RECITALS}>
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX dct: <http://purl.org/dc/terms/>

    SELECT *
    WHERE {{

        BIND(
            <{RECITALS}assessment_{assessment_id}>
            AS ?assessment
        )

        ?assessment
            a recitals:ComplianceAssessment ;
            recitals:belongsToUseCase ?use_case ;
            recitals:assesses ?requirement ;
            recitals:law ?law ;
            recitals:article ?article ;
            recitals:assessmentStatus ?status ;
            recitals:hasReport ?report ;
            dct:created ?timestamp .

        ?report
            a recitals:ValidationReport ;
            sh:conforms ?conforms .

        OPTIONAL {{

            ?report
                recitals:hasFinding ?finding .

            OPTIONAL {{
                ?finding recitals:message ?message .
            }}

            OPTIONAL {{
                ?finding recitals:severity ?severity .
            }}

            OPTIONAL {{
                ?finding recitals:focusNode ?focusNode .
            }}

            OPTIONAL {{
                ?finding recitals:property ?property .
            }}

            OPTIONAL {{
                ?finding recitals:requirementId ?requirementId .
            }}
        }}
    }}
    ORDER BY ?finding
    """

    results = query_fuseki(query)

    bindings = results["results"]["bindings"]

    if not bindings:

        raise HTTPException(
            status_code=404,
            detail="Assessment not found"
        )

    first = bindings[0]

    findings = []

    seen = set()

    violations = 0
    warnings = 0

    for row in bindings:

        if "finding" not in row:
            continue

        finding_uri = row["finding"]["value"]

        if finding_uri in seen:
            continue

        seen.add(finding_uri)

        severity = (
            row["severity"]["value"]
            if "severity" in row
            else "Violation"
        )

        if severity.lower() == "violation":
            violations += 1

        elif severity.lower() == "warning":
            warnings += 1

        findings.append({

            "requirement_id":
                row["requirementId"]["value"]
                if "requirementId" in row
                else None,

            "severity":
                severity,

            "message":
                row["message"]["value"]
                if "message" in row
                else None,

            "focus_node":
                row["focusNode"]["value"]
                if "focusNode" in row
                else None,

            "property":
                row["property"]["value"]
                if "property" in row
                else None

        })

    return {

        "assessment": {

            "id":
                assessment_id,

            "uri":
                first["assessment"]["value"],

            "timestamp":
                first["timestamp"]["value"],

            "status":
                first["status"]["value"],

            "conforms":
                first["conforms"]["value"].lower() == "true"

        },

        "use_case": {

            "id":
                first["use_case"]["value"].rsplit("/", 1)[-1],

            "uri":
                first["use_case"]["value"]

        },

        "requirement": {

            "law":
                first["law"]["value"].rsplit("/",1)[-1],

            "article":
                int(first["article"]["value"]),

            "identifier":
                first["requirement"]["value"].rsplit("/",1)[-1]

        },

        "summary": {

            "total_findings":
                len(findings),

            "violations":
                violations,

            "warnings":
                warnings

        },

        "findings":
            findings

    }