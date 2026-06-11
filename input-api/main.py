import uuid

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import XSD
import requests
from enum import Enum

class ServiceType(str, Enum):
    serviceA = "ServiceA"
    serviceB = "ServiceB"
    serviceC = "ServiceC"

class ComponentType(str, Enum):
    anonymization = "Anonymization"
    cryptography = "Cryptography"
    dlt = "DistributedLedger"

class StatusType(str, Enum):
    pass_ = "Pass"
    fail = "Fail"
app = FastAPI()

EX = Namespace("http://example.org/metadata/")

@app.post("/input")
async def upload_rdf(
    file: UploadFile = File(...),
    service: ServiceType = Form(...),
    component: ComponentType = Form(...),
    component_status: StatusType = Form(...)
):
    version_id = str(uuid.uuid4())

    graph_uri = f"http://example.org/version/{version_id}"
    fuseki_url = f"http://fuseki:3030/dataset/data?graph={graph_uri}"
    
    content = await file.read()
    # Step 1: Detect RDF format automatically
    g = Graph()
    formats = ["turtle", "xml", "json-ld", "nt"]

    parsed = False
    detected_format = None

    for fmt in formats:
        try:
            g.parse(data=content, format=fmt)
            parsed = True
            detected_format = fmt
            break
        except:
            continue

    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid RDF format")

    # Step 2: Insert original RDF
    content_types = {
        "turtle": "text/turtle",
        "xml": "application/rdf+xml",
        "json-ld": "application/ld+json",
        "nt": "application/n-triples"
    }

    response = requests.post(
        fuseki_url,
        data=content,
        headers={"Content-Type": content_types[detected_format]},
        auth=("admin", "admin")
    )

    if response.status_code not in [200, 201]:
        raise HTTPException(
            status_code=500,
            detail=f"Fuseki error: {response.text}"
        )

    # Step 3: Store metadata as RDF 🔥
    metadata_graph = Graph()
    metadata_graph.bind("", EX)

    run_uri = EX[f"version_{version_id}"]

    metadata_graph.add((run_uri, EX.component, EX[component.value]))
    metadata_graph.add((run_uri, EX.serviceId, EX[service.value]))
    metadata_graph.add((run_uri, EX.componentStatus, Literal(component_status.value)))
    metadata_graph.add((run_uri, EX.timestamp, Literal(str(version_id), datatype=XSD.string)))

    rdf_metadata = metadata_graph.serialize(format="turtle")

    response = requests.post(
        fuseki_url,
        data=rdf_metadata,
        headers={"Content-Type": "text/turtle"},
        auth=("admin", "admin")
    )

    if response.status_code not in [200, 201]:
        raise HTTPException(
            status_code=500,
            detail=f"Metadata insert error: {response.text}"
        )

    return {
        "message": "RDF + metadata inserted successfully",
        "service": service,
        "component": component,
        "version_id": version_id,
        "component_status": component_status
    }