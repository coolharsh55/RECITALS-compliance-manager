"""
RECITALS Input API

Responsibilities:
- Create and manage use cases
- Upload RDF knowledge
- Store RDF in triple store
- Associate submitted resources with use cases
- Maintain provenance of submissions

Compliance checking is handled by the Compliance API.
"""

import copy
import os
import uuid
import re
from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
import requests
from rdflib import URIRef
from rdflib.namespace import XSD
from datetime import datetime

from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi import (
    FastAPI,
    File,
    Form,
    UploadFile,
    HTTPException
)



from rdflib import (
    Graph,
    Literal,
    Namespace,
    URIRef
)

from rdflib.namespace import (
    RDF,
    RDFS,
    XSD
)


# --------------------------------------------------
# Application
# --------------------------------------------------

app = FastAPI(
    title="RECITALS Input API"
)

# The compliance web interface (compliance-api /ui) uploads
# data and creates use cases from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "UI_ORIGINS",
        "http://localhost:8001,http://127.0.0.1:8001"
    ).split(","),
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Namespaces
# --------------------------------------------------

RECITALS = Namespace("http://example.org/recitals/")
DPV = Namespace("https://w3id.org/dpv#")
PROV = Namespace("http://www.w3.org/ns/prov#")

DC = Namespace("http://www.w3.org/ns/dc#")

# --------------------------------------------------
# Fuseki configuration
# --------------------------------------------------

FUSEKI_DATA_URL = os.getenv(
    "FUSEKI_DATA_URL",
    "http://fuseki:3030/dataset/data"
)

FUSEKI_QUERY_URL = os.getenv(
    "FUSEKI_QUERY_URL",
    "http://fuseki:3030/dataset/query"
)

FUSEKI_USER = os.getenv("FUSEKI_USER")
FUSEKI_PASSWORD = os.getenv("FUSEKI_PASSWORD")

# Credentials come from the environment (.env via docker-compose).
if not FUSEKI_USER or not FUSEKI_PASSWORD:
    raise RuntimeError(
        "FUSEKI_USER and FUSEKI_PASSWORD must be set "
        "(copy .env.example to .env)"
    )

FUSEKI_UPDATE_URL = os.getenv(
    "FUSEKI_UPDATE_URL",
    "http://fuseki:3030/dataset/update"
)

USE_CASE_ID_PATTERN = (
    r"[A-Za-z][A-Za-z0-9_-]{0,79}"
)



# --------------------------------------------------
# Models
# --------------------------------------------------
class Law(str, Enum):
    """Laws a use case can be assessed against."""
    GDPR = "GDPR"
    NIS2 = "NIS2"
    EU_AI_ACT = "EU_AI_ACT"

# Development only.
# In the production RECITALS system this enum will be replaced by
# a dynamic dropdown populated from GET /use-cases, which queries
# the triple store.
    
class UseCaseCreate(BaseModel):
    """Request body model for creating a use case (not used by the form-based endpoints)."""
    label: str
    laws: List[Law]
    use_case_id: Optional[str] = None

# --------------------------------------------------
# Validation helpers
# --------------------------------------------------

def validate_use_case_id(
    use_case_id: str
):

    """Reject (422) a use case id that does not match USE_CASE_ID_PATTERN."""
    if not re.fullmatch(
        USE_CASE_ID_PATTERN,
        use_case_id
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Invalid use case identifier: start with a letter, "
                "then use only letters, numbers, '_' or '-' "
                "(at most 80 characters)"
            )
        )



def use_case_uri(
    use_case_id: str
):

    """Return the URI that identifies a use case."""
    return RECITALS[use_case_id]



def use_case_graph_uri(
    use_case_id: str
):

    # Named graph holding the RDF submitted for one use case.
    # The Compliance API validates exactly this graph.
    """Return the named graph that holds a use case's uploaded data."""
    return RECITALS["graph/" + use_case_id]



# --------------------------------------------------
# RDF parsing
# --------------------------------------------------

def parse_turtle(
    content: bytes
) -> Graph:

    """Parse uploaded bytes as UTF-8 Turtle; answer 400 if they are not valid."""
    try:
        turtle = content.decode(
            "utf-8"
        )

    except UnicodeDecodeError:

        raise HTTPException(
            status_code=400,
            detail="File must be UTF-8 Turtle RDF"
        )


    graph = Graph()

    try:

        graph.parse(
            data=turtle,
            format="turtle"
        )

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid Turtle RDF"
        )


    return graph



# --------------------------------------------------
# Triple store operations
# --------------------------------------------------

def store_graph(
    graph: Graph,
    graph_uri: Optional[str] = None
):

    """Add a graph to Fuseki, into the named graph graph_uri or the default graph."""
    try:

        # Graph Store Protocol upload; without a graph name it goes to the default graph
        response = requests.post(

            FUSEKI_DATA_URL,

            params=(
                {"graph": str(graph_uri)}
                if graph_uri
                else None
            ),

            data=graph.serialize(
                format="turtle"
            ),

            headers={
                "Content-Type":
                "text/turtle; charset=utf-8"
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


    # Fuseki answers 200, 201 or 204 when the data is stored
    if response.status_code not in (
        200,
        201,
        204
    ):

        raise HTTPException(
            status_code=502,
            detail="Triple store rejected RDF"
        )




def query_fuseki(
    query: str
):

    """Run a SPARQL query on Fuseki and return the JSON results."""
    try:

        # SPARQL query over HTTP; results come back as SPARQL JSON
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
            detail="SPARQL query failed"
        )


    return response.json()



# --------------------------------------------------
# Use case functions
# --------------------------------------------------

def use_case_exists(
    use_case_id: str
):

    """Return True if a use case with this id is stored in Fuseki."""
    resource = use_case_uri(
        use_case_id
    )


    query = f"""

    ASK

    WHERE {{

        <{resource}>
            a
            <{RECITALS.UseCase}>

    }}

    """


    result = query_fuseki(
        query
    )


    return result.get(
        "boolean",
        False
    )



def get_root_resources(
    graph: Graph
):

    """Return the resources typed recitals:UseCaseResource in an uploaded graph."""
    resources = []


    for resource in graph.subjects(
        RDF.type,
        RECITALS.UseCaseResource
    ):

        resources.append(
            resource
        )


    return resources



# --------------------------------------------------
# API endpoints
# --------------------------------------------------


# @app.post("/use-cases", status_code=201)

# def create_use_case(
#     use_case_id: UseCase = Form(...),
#     law: Law = Form(...),
#     label: str = Form(...)
# ):

#     resource = use_case_uri(use_case_id.value)

#     if use_case_exists(use_case_id):
#         raise HTTPException(
#             status_code=409,
#             detail=f"Use case '{use_case_id}' already exists."
#         )
    
#     graph = Graph()
#     graph.bind("recitals", RECITALS)
#     graph.bind("prov", PROV)
#     graph.bind("rdfs", RDFS)

#     graph.add((resource, RDF.type, RECITALS.UseCase))
#     graph.add((resource, RDFS.label, Literal(label)))

#     graph.add((
#         resource,
#         RECITALS.hasApplicableLaw,
#         RECITALS[law.value]
#     ))


#     graph.add((
#         resource,
#         PROV.generatedAtTime,
#         Literal(datetime.utcnow().isoformat(), datatype=XSD.dateTime)
#     ))

#     graph.add((
#         resource,
#         PROV.wasAttributedTo,
#         Literal("RECITALS Input API")
#     ))

#     # Store only if it is a new use case
#     store_graph(graph)

#     return {
#         "message": "Use case created successfully",
#         "use_case_id": use_case_id.value,
#         "label": label,
#         "applicable_law": law.value,
#         "created_at": datetime.utcnow().isoformat() + "Z",
#         "uri": str(resource)
#     }

@app.post("/use-cases", status_code=201)
def create_use_case(
    use_case_id: str = Form(...),
    law: Law = Form(...),
    label: str = Form(...)
):

    # if not use_case_id:
    #     use_case_id = "UC-" + str(uuid.uuid4())

    """POST /use-cases: create a use case with its id, label and first law (409 if the id exists)."""
    validate_use_case_id(use_case_id)

    # Do not create the use case again
    if use_case_exists(use_case_id):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Use case {use_case_id} already exists; "
                "use PATCH /use-cases/{id}/laws to add a law to it"
            )
        )

    graph = Graph()

    graph.bind("recitals", RECITALS)
    graph.bind("dc", DC)

    resource = use_case_uri(use_case_id)

    # Use case
    graph.add((resource, RDF.type, RECITALS.UseCase))
    # Label
    graph.add((resource, RDFS.label, Literal(label)))
    graph.add((resource, RECITALS.hasApplicableLaw, RECITALS[law.value]))

    # Creation timestamp
    created_at = datetime.now(timezone.utc)
    graph.add((resource, DC.created, Literal(created_at,datatype=XSD.dateTime)))
    
	
    # Store only if it is a new use case
    store_graph(graph)

    return {
        "message": "Use case created successfully",
        "use_case_id": use_case_id,
        "label": label,
        "applicable_laws": law.value ,
        "created_at": created_at.isoformat(),
        "uri": str(resource)
    }

@app.get("/use-cases")
def list_use_cases():

    """GET /use-cases: list the stored use cases with their laws and dates."""
    query = f"""
    PREFIX recitals: <{RECITALS}>
    PREFIX rdfs: <{RDFS}>
    PREFIX dc: <{DC}>

    SELECT ?uc ?label ?law ?created ?modified
    WHERE {{
        ?uc a recitals:UseCase ;
            rdfs:label ?label ;
            recitals:hasApplicableLaw ?law .

        OPTIONAL {{
            ?uc dc:created ?created .
        }}

        OPTIONAL {{
            ?uc dc:modified ?modified .
        }}
    }}

    ORDER BY ?uc
    """

    results = query_fuseki(query)

    use_cases = {}

    for row in results["results"]["bindings"]:

        uri = row["uc"]["value"]
        use_case_id = uri.rsplit("/", 1)[-1]

        # Create the use case object only once
        if use_case_id not in use_cases:

            use_cases[use_case_id] = {
                "use_case_id": use_case_id,
                "label": row["label"]["value"],
                "applicable_laws": [],
                "created_at": None,
                "modified_at": None,
                "uri": uri
            }

        # Add applicable law
        law = row["law"]["value"].rsplit("/", 1)[-1]

        if law not in use_cases[use_case_id]["applicable_laws"]:
            use_cases[use_case_id]["applicable_laws"].append(law)

        # Add creation timestamp if it exists
        if "created" in row:
            use_cases[use_case_id]["created_at"] = (
                row["created"]["value"]
            )

        # Add modification timestamp if it exists
        if "modified" in row:
            use_cases[use_case_id]["modified_at"] = (
                row["modified"]["value"]
            )

    return list(use_cases.values())
    
# @app.get("/use-cases")
# def list_use_cases():

#     results = query_fuseki(query)

#     use_cases = {}

#     for row in results["results"]["bindings"]:

#         use_case_id = row["uc"]["value"].split("/")[-1]

#         if use_case_id not in use_cases:

#             use_cases[use_case_id] = {
#                 "use_case_id": use_case_id,
#                 "label": row["label"]["value"],
#                 "applicable_laws": [],
#                 "created_at": row.get("created", {}).get("value"),
#                 "uri": row["uc"]["value"]
#             }

#         law = row["law"]["value"].split("/")[-1]

#         if law not in use_cases[use_case_id]["applicable_laws"]:
#             use_cases[use_case_id]["applicable_laws"].append(law)

#     return list(use_cases.values())

@app.patch("/use-cases/{use_case_id}/laws")
def add_law_to_use_case(
    use_case_id: str,
    law: Law = Form(...)
):

    """PATCH /use-cases/{use_case_id}/laws: add another applicable law to a use case."""
    validate_use_case_id(use_case_id)

    if not use_case_exists(use_case_id):
        raise HTTPException(
            status_code=404,
            detail="Use case not found"
        )

    resource = use_case_uri(use_case_id)

    # Add the law and replace the modification date in one update
    modified_at = datetime.now(timezone.utc)

    query = f"""
    PREFIX recitals: <{RECITALS}>
    PREFIX dc: <{DC}>
    PREFIX xsd: <{XSD}>

    DELETE {{
        <{resource}> dc:modified ?oldModified .
    }}

    INSERT {{
        <{resource}>
            recitals:hasApplicableLaw recitals:{law.value} ;
            dc:modified "{modified_at.isoformat()}"^^xsd:dateTime .
    }}

    WHERE {{
        OPTIONAL {{
            <{resource}> dc:modified ?oldModified .
        }}
    }}
    """

    update_fuseki(query)

    return {
        "message": "Applicable law updated successfully",
        "use_case_id": use_case_id,
        "added_law": law.value,
        "modified_at": modified_at.isoformat(),
        "uri": str(resource)
    }

def update_fuseki(query: str):

    """Run a SPARQL update on Fuseki."""
    try:
        response = requests.post(
            FUSEKI_UPDATE_URL,
            data=query,
            headers={
                "Content-Type": "application/sparql-update"
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

    if response.status_code not in (200, 204):
        raise HTTPException(
            status_code=502,
            detail="Triple store update failed"
        )

# def update_fuseki(update: str) -> None:
#     try:
#         response = requests.post(
#             FUSEKI_UPDATE_URL,
#             data=update,
#             headers={"Content-Type": "application/sparql-update"},
#             auth=(FUSEKI_USER, FUSEKI_PASSWORD),
#             timeout=15,
#         )
#     except requests.RequestException:
#         raise HTTPException(
#             status_code=503,
#             detail="The triple store is unavailable"
#         )

#     if response.status_code not in (200, 204):
#         raise HTTPException(
#             status_code=502,
#             detail="The triple store update failed"
#         )
    
def insert_law(use_case_id: str, law: Law):

    """Add an applicable law to a use case in Fuseki."""
    query = f"""
    PREFIX recitals: <{RECITALS}>

    INSERT DATA {{
        <{use_case_uri(use_case_id)}>
            recitals:hasApplicableLaw
            recitals:{law.value} .
    }}
    """

    update_fuseki(query)

@app.post(
    "/input",
    status_code=201
)
async def upload_input(

    file: UploadFile = File(...),

    use_case_id: str = Form(...)

):


    """POST /input: store an uploaded Turtle file in the use case's named graph and record the submission."""
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


    content = await file.read()


    if not content:

        raise HTTPException(
            status_code=400,
            detail="Empty file"
        )


    rdf = parse_turtle(
        content
    )


    #
    # Store submitted RDF
    #

    store_graph(
        rdf,
        use_case_graph_uri(use_case_id)
    )



    #
    # Create metadata
    #

    metadata = Graph()


    submission = RECITALS[
        "Submission-"
        +
        str(uuid.uuid4())
    ]


    metadata.add(
        (
            submission,
            RDF.type,
            RECITALS.InputSubmission
        )
    )


    metadata.add(
        (
            submission,
            PROV.generatedAtTime,
            Literal(
                datetime.now(
                    timezone.utc
                ),
                datatype=XSD.dateTime
            )
        )
    )


    metadata.add(
        (
            submission,
            RECITALS.submittedFor,
            use_case_uri(use_case_id)
        )
    )



    #
    # Link root resources
    #

    resources = get_root_resources(
        rdf
    )


    for resource in resources:

        metadata.add(
            (
                use_case_uri(use_case_id),
                RECITALS.includes,
                resource
            )
        )


        metadata.add(
            (
                submission,
                RECITALS.containsResource,
                resource
            )
        )


    store_graph(
        metadata
    )


    return {

        "message":
        "Input stored successfully",

        "use_case":
        use_case_id,

        "submission":
        str(submission),

        "linked_resources":
        [
            str(r)
            for r in resources
        ]

    }


# ============================================================
# Use case dropdowns on /docs
# ============================================================

# Parameters and form fields that take an existing use case.
# Creating a use case (POST /use-cases) stays free text.
USE_CASE_FIELDS = [
    ("/input", "post", "use_case_id"),
    ("/use-cases/{use_case_id}/laws", "patch", "use_case_id"),
]


def openapi_with_use_cases():

    """
    The /docs page offers the use cases stored in Fuseki as a
    dropdown. The schema is rebuilt on every request so new use
    cases appear after a reload; if Fuseki cannot be reached the
    fields stay free text.
    """

    schema = copy.deepcopy(
        get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes
        )
    )

    try:
        ids = sorted({u["use_case_id"] for u in list_use_cases()})
    except Exception:
        return schema

    if not ids:
        return schema

    def dropdown(old):
        """Return a schema that offers the given values as a dropdown."""
        return {
            "type": "string",
            "enum": ids,
            "title": old.get("title", "Use case"),
            "description": "Existing use cases. Created a new one? Reload this page to see it in the list."
        }

    for path, method, field in USE_CASE_FIELDS:

        operation = schema["paths"][path][method]

        for parameter in operation.get("parameters", []):
            if parameter["name"] == field:
                parameter["schema"] = dropdown(parameter["schema"])

        for media in operation.get("requestBody", {}).get("content", {}).values():
            ref = media["schema"].get("$ref")
            if ref:
                properties = schema["components"]["schemas"][ref.rsplit("/", 1)[-1]]["properties"]
                if field in properties:
                    properties[field] = dropdown(properties[field])

    return schema


app.openapi = openapi_with_use_cases
