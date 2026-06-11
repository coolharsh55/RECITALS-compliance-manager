from fastapi import APIRouter, UploadFile, File, HTTPException
from rdflib import Graph

#app = FastAPI()
router = APIRouter()

#@app.post("/check-rdf/")
@router.post("/check-rdf/")
async def check_rdf_file(file: UploadFile = File(...)):
    try:
        content = await file.read()

        g = Graph()

        # Try parsing as RDF (auto-detect format)
        g.parse(data=content)

        return {
            "status": "success",
            "message": "File is a valid RDF file",
            "triples_count": len(g)
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid RDF file: {str(e)}"
        )
    
    