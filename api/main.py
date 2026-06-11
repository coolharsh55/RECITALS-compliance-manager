from fastapi import FastAPI
from api.compliance_requirement import router as rdf_router
from api.shacl_validation import router as shacl_router

app = FastAPI()

# app.include_router(rdf_router)
# app.include_router(shacl_router)

app.include_router(rdf_router, prefix="/rdf", tags=["RDF Checks"])
app.include_router(shacl_router, prefix="/shacl", tags=["SHACL Validation"])