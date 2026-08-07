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

FUSEKI_USER = os.getenv(
    "FUSEKI_USER",
    "admin"
)

FUSEKI_PASSWORD = os.getenv(
    "FUSEKI_PASSWORD",
    "admin"
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
    GDPR = "GDPR"
    NIS2 = "NIS2"
    EU_AI_ACT = "EU_AI_ACT"

# Development only.
# In the production RECITALS system this enum will be replaced by
# a dynamic dropdown populated from GET /use-cases, which queries
# the triple store.
class UseCase(str, Enum):
    UC1 = "UC1"
    UC2 = "UC2"
    UC3 = "UC3"
    
class UseCaseCreate(BaseModel):
    label: str
    laws: List[Law]
    use_case_id: Optional[str] = None

class LawUpdate(BaseModel):
    use_case_id: UseCase
    law: List[Law]
    
# --------------------------------------------------
# Validation helpers
# --------------------------------------------------

def validate_use_case_id(
    use_case_id: str
):

    if not re.fullmatch(
        USE_CASE_ID_PATTERN,
        use_case_id
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Invalid use case identifier"
            )
        )



def use_case_uri(
    use_case_id: str
):

    return RECITALS[use_case_id]



# --------------------------------------------------
# RDF parsing
# --------------------------------------------------

def parse_turtle(
    content: bytes
) -> Graph:

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
    graph: Graph
):

    try:

        response = requests.post(

            FUSEKI_DATA_URL,

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
            detail="SPARQL query failed"
        )


    return response.json()



# --------------------------------------------------
# Use case functions
# --------------------------------------------------

def use_case_exists(
    use_case_id: str
):

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
    use_case_id: UseCase = Form(...),
    law: Law = Form(...),
    label: str = Form(...)
):

    # if not use_case_id:
    #     use_case_id = "UC-" + str(uuid.uuid4())

    validate_use_case_id(use_case_id)

    # Do not create the use case again
    if use_case_exists(use_case_id):
        return {
            "message": "Use case already exists",
            "use_case_id": use_case_id,
            "uri": str(use_case_uri(use_case_id))
        }

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
        "use_case_id": use_case_id.value,
        "label": label,
        "applicable_laws": law.value ,
        "created_at": created_at.isoformat(),
        "uri": str(resource)
    }

@app.get("/use-cases")
def list_use_cases():

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

# @app.patch("/use_cases/laws")
# def update_use_case(
#     use_case: UseCase = Form(...),
#     law: Law = Form(...)
# ):
#     use_case_id = use_case.value

#     validate_use_case_id(use_case_id)

#     if not use_case_exists(use_case_id):
#         raise HTTPException(
#             status_code=404,
#             detail="Use case not found"
#         )

#     query = f"""
#     PREFIX recitals: <{RECITALS}>

#     INSERT DATA {{
#         <{use_case_uri(use_case_id)}>
#             recitals:hasApplicableLaw
#             recitals:{law.value} .
#     }}
#     """

#     update_fuseki(query)

#     return {
#         "message": "Applicable law updated",
#         "use_case_id": use_case_id,
#         "added_law": law.value,
#     }

@app.patch("/use_cases/laws")
def update_use_case(
    use_case: UseCase = Form(...),
    law: Law = Form(...)
):

    use_case_id = use_case.value

    validate_use_case_id(use_case_id)

    if not use_case_exists(use_case_id):
        raise HTTPException(
            status_code=404,
            detail="Use case not found"
        )

    resource = use_case_uri(use_case_id)

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


    validate_use_case_id(
        use_case_id
    )


    if not use_case_exists(
        use_case_id
    ):

        raise HTTPException(
            status_code=404,
            detail="Use case does not exist"
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
        rdf
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