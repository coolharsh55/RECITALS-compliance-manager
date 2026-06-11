from rdflib import Graph, Namespace
from pyshacl import validate

# Namespaces
SH = Namespace("http://www.w3.org/ns/shacl#")

# -------- FILE PATHS --------
DATA_FILE = "data.ttl"
SHAPES_FILE = "shapes.ttl"

# -------- LOAD GRAPHS --------
data_graph = Graph()
data_graph.parse(DATA_FILE, format="turtle")

shapes_graph = Graph()
shapes_graph.parse(SHAPES_FILE, format="turtle")

# -------- RUN SHACL VALIDATION --------
conforms, report_graph, report_text = validate(
    data_graph=data_graph,
    shacl_graph=shapes_graph,
    inference='rdfs',          # enable RDFS inference
    abort_on_first=False,
    allow_infos=True,
    allow_warnings=True,
    meta_shacl=False,
    debug=False
)

# -------- PRINT RESULTS --------
print("\n==============================")
print("SHACL Validation Result")
print("==============================")

if conforms:
    print("Data conforms to SHACL shapes.")
else:
    print("Data does NOT conform to SHACL shapes.")

#print("\n--- Validation Report ---")
#print(report_text)

print("Findings:\n")

for result in report_graph.subjects(predicate=SH.resultSeverity):
    
    severity = report_graph.value(result, SH.resultSeverity)
    message = report_graph.value(result, SH.resultMessage)
    focus = report_graph.value(result, SH.focusNode)
    path = report_graph.value(result, SH.resultPath)

    severity_label = severity.split("#")[-1]

    print(f"[{severity_label}]")
    print(f" Node     : {focus}")
    
    if path:
        print(f" Property : {path}")
    
    print(f" Message  : {message}")
    print("-" * 40)
    
# Optional: Save report to file
report_graph.serialize(destination="validation_report.ttl", format="turtle")