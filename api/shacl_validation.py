from fastapi import APIRouter, UploadFile, File
from fastapi.responses import Response
from rdflib import Graph, Namespace
from pyshacl import validate
import uuid
from api.triplestore import insert_rdf  

#app = FastAPI()
router = APIRouter()

SH = Namespace("http://www.w3.org/ns/shacl#")
SHAPES_FILE = "shapes.ttl"

# Shared validation logic 
def run_shacl_validation(data_content: bytes):

    data_graph = Graph()
    data_graph.parse(data=data_content.decode(), format="turtle")

    shapes_graph = Graph()
    shapes_graph.parse(SHAPES_FILE, format="turtle")

    conforms, report_graph, report_text = validate(
        data_graph=data_graph,
        shacl_graph=shapes_graph,
        inference="rdfs",
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True,
        meta_shacl=False,
        debug=False
    )
    return conforms, report_graph
   
# Endpoint 1: JSON response (for apps, UI, analysis)
#@app.post("/validate")
@router.post("/validate/")

async def validate_json(file: UploadFile = File(...)): 
    
    data_content = await file.read()
    conforms, report_graph = run_shacl_validation(data_content)
    #shapes_content = await shapes.read()

     # 2. Generate unique graph ID
    graph_id = str(uuid.uuid4())
    graph_uri = f"http://example.org/data/{graph_id}"

    # 3. Insert into Fuseki
    insert_rdf(data_content, graph_uri)

    findings = []

    for result in report_graph.subjects(predicate=SH.resultSeverity):

        severity = report_graph.value(result, SH.resultSeverity)
        message = report_graph.value(result, SH.resultMessage)
        focus = report_graph.value(result, SH.focusNode)
        path = report_graph.value(result, SH.resultPath)

        findings.append({
            "severity": str(severity).split("#")[-1],
            "node": str(focus),
            "property": str(path) if path else None,
            "message": str(message)
        })

    return {
        "conforms": conforms,
        "findings": findings
    }

# Endpoint 2: File download (TTL report)
#@app.post("/validate/file")
@router.post("/validate/file")

async def validate_file(file: UploadFile = File(...)):

    data_content = await file.read()
    conforms, report_graph = run_shacl_validation(data_content)

    report_ttl = report_graph.serialize(format="turtle")

    return Response(
        content=report_ttl,
        media_type="text/turtle",
        headers={
            "Content-Disposition": "attachment; filename=validation_report.ttl"
        }
    )