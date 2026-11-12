"""RECITALS Status API.

Returns the latest stored assessment result for a use case, law and
article."""

import copy
from enum import Enum
import os
import re

import requests
from fastapi import FastAPI, HTTPException
from fastapi.openapi.utils import get_openapi


class Law(str, Enum):
    """Laws a status can be requested for."""
    gdpr = "GDPR"
    nis2 = "NIS2"
    eu_ai_act = "EU_AI_ACT"


app = FastAPI(title="RECITALS Status API")
FUSEKI_QUERY_URL = os.getenv("FUSEKI_QUERY_URL", "http://fuseki:3030/dataset/query")
FUSEKI_USER = os.getenv("FUSEKI_USER")
FUSEKI_PASSWORD = os.getenv("FUSEKI_PASSWORD")

# Credentials come from the environment (.env via docker-compose).
if not FUSEKI_USER or not FUSEKI_PASSWORD:
    raise RuntimeError("FUSEKI_USER and FUSEKI_PASSWORD must be set (copy .env.example to .env)")
RECITALS = "http://example.org/recitals/"

# Articles assessed by the Compliance API (its ASSESSMENTS table).
ARTICLES = {
    "GDPR": [30, 32],
    "NIS2": [20, 21],
    "EU_AI_ACT": [10, 11],
}


def query_fuseki(query: str) -> dict:
    """Run a SPARQL query on Fuseki and return the JSON results (502 on failure)."""
    response = requests.post(FUSEKI_QUERY_URL, data=query, headers={"Content-Type": "application/sparql-query", "Accept": "application/sparql-results+json"}, auth=(FUSEKI_USER, FUSEKI_PASSWORD), timeout=15)
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Query failed")
    return response.json()


def existing_use_case_ids() -> list:
    """Return the ids of the use cases stored in Fuseki."""
    results = query_fuseki(f"SELECT ?uc WHERE {{ ?uc a <{RECITALS}UseCase> }}")
    return [row["uc"]["value"].rsplit("/", 1)[-1] for row in results["results"]["bindings"]]


@app.get("/status")
def get_status(use_case_id: str, law: Law = Law.gdpr, article: int = 30):
    """Return the latest stored result for one use case and legal assessment."""
    # Validate the request before querying Fuseki
    if article not in ARTICLES[law.value]:
        raise HTTPException(status_code=400, detail=f"Article {article} is not supported for {law.value}. Supported articles: {ARTICLES[law.value]}")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", use_case_id):
        raise HTTPException(status_code=422, detail="use_case_id may contain only letters, numbers, underscores, and hyphens")
    if not query_fuseki(f"ASK {{ <{RECITALS}{use_case_id}> a <{RECITALS}UseCase> }}").get("boolean", False):
        raise HTTPException(status_code=404, detail="Use case not found")
    # Must match the triples written by store_result in the Compliance API.
    query = f'''PREFIX recitals: <{RECITALS}>
PREFIX dct: <http://purl.org/dc/terms/>
SELECT ?status ?time WHERE {{
  ?run a recitals:ComplianceAssessment ;
       recitals:belongsToUseCase <{RECITALS}{use_case_id}> ;
       recitals:law recitals:{law.value} ;
       recitals:article {article} ;
       recitals:assessmentStatus ?status ;
       dct:created ?time .
}} ORDER BY DESC(?time) LIMIT 1'''
    bindings = query_fuseki(query)["results"]["bindings"]
    # No stored assessment yet for this use case, law and article
    if not bindings:
        return {"use_case_id": use_case_id, "law": law, "article": article, "status": "not_found"}
    result = bindings[0]
    return {"use_case_id": use_case_id, "law": law, "article": article,
            "status": result["status"]["value"], "timestamp": result["time"]["value"]}


# ============================================================
# Use case dropdowns on /docs
# ============================================================

# Parameters and form fields that take an existing use case.
# Creating a use case (POST /use-cases) stays free text.
USE_CASE_FIELDS = [
    ("/status", "get", "use_case_id"),
]

ARTICLE_FIELDS = [
    ("/status", "get", "article"),
]


def openapi_with_use_cases():

    """
    The /docs page offers the use cases stored in Fuseki and the
    supported article numbers as dropdowns. The schema is rebuilt
    on every request so new use cases appear after a reload; if
    Fuseki cannot be reached the use case fields stay free text.
    """

    schema = copy.deepcopy(
        get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes
        )
    )

    set_choices(
        schema,
        ARTICLE_FIELDS,
        "integer",
        sorted({a for articles in ARTICLES.values() for a in articles}),
        " · ".join(f"{law}: {', '.join(map(str, articles))}" for law, articles in ARTICLES.items())
    )

    try:
        ids = sorted(set(existing_use_case_ids()))
    except Exception:
        return schema

    if ids:
        set_choices(schema, USE_CASE_FIELDS, "string", ids,
                    "Existing use cases. Created a new one? Reload this page to see it in the list.")

    return schema


def set_choices(schema, fields, value_type, values, description=None):

    """
    Turn the given parameters and form fields into a fixed list of
    choices, which Swagger shows as a dropdown.
    """

    def dropdown(old):
        """Return a schema that offers the given values as a dropdown."""
        new = {
            "type": value_type,
            "enum": values,
            "title": old.get("title", "")
        }
        if description:
            new["description"] = description
        if old.get("default") in values:
            new["default"] = old["default"]
        return new

    for path, method, field in fields:

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


app.openapi = openapi_with_use_cases
