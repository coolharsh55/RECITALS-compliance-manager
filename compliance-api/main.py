from fastapi import FastAPI, HTTPException
from rdflib import Graph, Namespace, URIRef, Literal
from pyshacl import validate
import requests
from datetime import datetime
from rdflib.namespace import RDF, Namespace
import uuid
from rdflib.namespace import XSD
from enum import Enum

class ServiceID(str, Enum):
    service_a = "ServiceA"
    service_b = "ServiceB"
    service_c = "ServiceC"

class ComplianceType(str, Enum):
    gdpr30 = "gdpr30"
    gdpr32 = "gdpr32"

app = FastAPI()

FUSEKI_QUERY_URL = "http://fuseki:3030/dataset/query"
FUSEKI_UPDATE_URL = "http://fuseki:3030/dataset/update"

SH = Namespace("http://www.w3.org/ns/shacl#")
DCT = Namespace("http://purl.org/dc/terms/")
EX = Namespace("http://example.org/metadata/")

SHAPES_FILE = "shapes.ttl"


@app.post("/validate")
def validate_data(
    service: ServiceID,
    compliance_type: ComplianceType,
    version_id: str
):
    if compliance_type == ComplianceType.gdpr30:
        SHAPES_FILE = "shapes_gdpr30.ttl"
    elif compliance_type == ComplianceType.gdpr32:
        SHAPES_FILE = "shapes_gdpr32.ttl"
    else:
        raise HTTPException(status_code=400, detail="Unknown compliance type")

    # Step 1: Fetch all data
    graph_uri = f"http://example.org/version/{version_id}"

    query = f"""
    CONSTRUCT {{ ?s ?p ?o }}
    WHERE {{
        GRAPH <{graph_uri}> {{
            ?s ?p ?o
        }}
    }}
    """
    response = requests.post(
        FUSEKI_QUERY_URL,
        data=query,
        headers={"Content-Type": "application/sparql-query"},
        auth=("admin", "admin")
    )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch data")

    data_graph = Graph()
    data_graph.parse(data=response.text, format="turtle")

    # Step 2: Load SHACL shapes
    shapes_graph = Graph()
    shapes_graph.parse(SHAPES_FILE, format="turtle")

    # Step 3: Run SHACL validation
    conforms, report_graph, _ = validate(
        data_graph,
        shacl_graph=shapes_graph,
        inference="rdfs",
        debug=False
    )

    # Step 4: Extract violations
    violations = []

    for result in report_graph.subjects(RDF.type, SH.ValidationResult):
        message = report_graph.value(result, SH.resultMessage)
        focus = report_graph.value(result, SH.focusNode)
        severity = report_graph.value(result, SH.resultSeverity)
        source_shape = report_graph.value(result, SH.sourceShape)
        rule_id = report_graph.value(source_shape, DCT.identifier)

        violations.append({
            "node": str(focus),
            "message": str(message),
            "severity": str(severity).split("#")[-1],
            "rule": str(rule_id) if rule_id else None
        })

    # Step 5: Store validation result as RDF
    g = Graph()
    g.bind("", EX)

    run_id = str(uuid.uuid4())
    run_uri = EX[f"validationRun_{run_id}"]
    version_uri = EX[f"version_{version_id}"]

    timestamp = datetime.utcnow().isoformat()
    status = "valid" if conforms else "invalid"

    # Link validation to version 
    g.add((run_uri, EX.belongsToVersion, version_uri))
    
    # Metadata
    g.add((run_uri, EX.validationStatus, Literal(status)))
    g.add((run_uri, EX.validationTimestamp, Literal(timestamp, datatype=XSD.dateTime)))
    g.add((run_uri, EX.complianceType, Literal(compliance_type)))
    g.add((run_uri, EX.serviceId, Literal(service)))

    # Violations
    for v in violations:
        violation_node = URIRef(f"{run_uri}/violation/{uuid.uuid4()}")

        g.add((run_uri, EX.hasViolation, violation_node))
        g.add((violation_node, EX.node, URIRef(v["node"])))
        g.add((violation_node, EX.message, Literal(v["message"])))
        g.add((violation_node, EX.severity, Literal(v["severity"])))

        if v["rule"]:
            g.add((violation_node, EX.rule, URIRef(v["rule"])))

    # Serialize ONCE (outside loop)
    rdf_data = g.serialize(format="turtle")

    response = requests.post(
        "http://fuseki:3030/dataset/data",
        data=rdf_data,
        headers={"Content-Type": "text/turtle"},
        auth=("admin", "admin")
    )

    if response.status_code not in [200, 201]:
        raise HTTPException(
            status_code=500,
            detail=f"Fuseki error: {response.text}"
        )

    return {
        "service": service,
        "compliance_type": compliance_type,
        "status": status,
        "conforms": conforms
    }