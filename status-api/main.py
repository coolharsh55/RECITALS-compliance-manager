from fastapi import FastAPI, HTTPException
import requests
from enum import Enum

class ComplianceType(str, Enum):
    gdpr30 = "gdpr30"
    gdpr32 = "gdpr32"

class ServiceID(str, Enum):
    service_a = "ServiceA"
    service_b = "ServiceB"
    service_c = "ServiceC"

app = FastAPI()

FUSEKI_QUERY_URL = "http://fuseki:3030/dataset/query"

@app.get("/status")
def get_status(
    service_id: ServiceID,
    compliance_type: ComplianceType,
    version_id: str):

    query = f"""
    PREFIX : <http://example.org/metadata/>

       SELECT ?status ?time
        WHERE {{       
            ?run :belongsToVersion :version_{version_id} ;
                :validationStatus ?status ;
                :validationTimestamp ?time  .
        }}
        ORDER BY DESC(?time)
        LIMIT 1
        """
    print(query)

    response = requests.post(
        FUSEKI_QUERY_URL,
        data=query,
        headers={
            "Content-Type": "application/sparql-query",
            "Accept": "application/sparql-results+json"
        },
        auth=("admin", "admin")
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"Query failed: {response.text}"
        )

    data = response.json()

    bindings = data["results"]["bindings"]

    if not bindings:
        return {
            "version_id": version_id,
            "compliance_type": compliance_type,
            "status": "not_found"
        }

    result = bindings[0]

    return {
        "version_id": version_id,
        "compliance_type": compliance_type,
        "status": result["status"]["value"],
        "timestamp": result["time"]["value"]
    }