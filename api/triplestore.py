import requests
from rdflib import Graph
from requests.auth import HTTPBasicAuth
import os

FUSEKI_URL = os.getenv("FUSEKI_URL", "http://fuseki:3030/ds")
FUSEKI_USER = os.getenv("FUSEKI_USER", "admin")
FUSEKI_PASSWORD = os.getenv("FUSEKI_PASSWORD", "admin")

def insert_rdf(data_content: bytes, graph_uri: str):
    
    g = Graph()
    g.parse(data=data_content, format="turtle")

    rdf_data = g.serialize(format="turtle")

    # Use the SPARQL Graph Store HTTP Protocol endpoint
    url = f"{FUSEKI_URL}/sparql?graph={graph_uri}"
    
    headers = {"Content-Type": "text/turtle"}
    
    response = requests.post(
        url,
        data=rdf_data,
        headers=headers,
        auth=HTTPBasicAuth(FUSEKI_USER, FUSEKI_PASSWORD)
    )
    
    print(">>> INSERTING RDF")
    print(">>> URL:", url)
    print(">>> STATUS:", response.status_code)
    print(">>> RESPONSE:", response.text)

    if response.status_code not in [200, 201, 204]:
        raise Exception(f"Insert failed with status {response.status_code}: {response.text}")