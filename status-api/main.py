from enum import Enum
import re
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException


class Law(str, Enum):
    gdpr = "GDPR"


app = FastAPI(title="RECITALS Status API")
FUSEKI_QUERY_URL = "http://fuseki:3030/dataset/query"
RESULTS_GRAPH = "http://example.org/assessments"


@app.get("/status")
def get_status(use_case_id: Optional[str] = None, law: Law = Law.gdpr, article: int = 30,
               version_id: Optional[str] = None, service_id: Optional[str] = None,
               compliance_type: Optional[str] = None):
    """Return the latest stored result for one use case and legal assessment."""
    # version_id/compliance_type keep the original status endpoint usable while
    # new clients get an explicit use-case/law/article contract.
    use_case_id = use_case_id or version_id
    if not use_case_id:
        raise HTTPException(status_code=422, detail="use_case_id is required")
    if compliance_type == "gdpr32":
        article = 32
    elif compliance_type == "gdpr30":
        article = 30
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", use_case_id):
        raise HTTPException(status_code=422, detail="use_case_id may contain only letters, numbers, underscores, and hyphens")
    query = f'''PREFIX recitals: <http://example.org/metadata/>
SELECT ?status ?time WHERE {{
  GRAPH <{RESULTS_GRAPH}> {{
    ?run recitals:belongsToUseCase recitals:usecase_{use_case_id} ;
         recitals:law "{law.value}" ;
         recitals:article {article} ;
         recitals:assessmentStatus ?status ;
         recitals:validationTimestamp ?time .
  }}
}} ORDER BY DESC(?time) LIMIT 1'''
    response = requests.post(FUSEKI_QUERY_URL, data=query, headers={"Content-Type": "application/sparql-query", "Accept": "application/sparql-results+json"}, auth=("admin", "admin"), timeout=15)
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Query failed")
    bindings = response.json()["results"]["bindings"]
    if not bindings:
        return {"use_case_id": use_case_id, "law": law, "article": article, "status": "not_found"}
    result = bindings[0]
    return {"use_case_id": use_case_id, "law": law, "article": article,
            "status": result["status"]["value"], "timestamp": result["time"]["value"]}
