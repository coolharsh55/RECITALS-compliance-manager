# RECITALS

RECITALS is a compliance management system that validates RDF data using SHACL shapes and stores/queries data using an Apache Jena Fuseki triple store. The system is fully containerized and orchestrated using Docker Compose.

---

# System Overview

The system consists of four main components:

- Apache Jena Fuseki (RDF Triple Store)  → stores RDF data
- Input API (data ingestion) → receives and writes RDF data
- Compliance API (SHACL validation) → validates data using SHACL rules
- Status API (compliance monitoring & reporting) → exposes results and system state


All services communicate through a Docker internal network.

---

# How to Run the Project

## 1. Install Docker

Install Docker Desktop:
https://www.docker.com/products/docker-desktop/

Verify installation:

```bash
docker --version
docker compose version
```
## 2. Clone the repository

```bash
git clone https://github.com/beyzayaman/recitals.git
cd recitals
```
## 3. Start the system

Run all services using Docker Compose:
The system runs 3 APIs + 1 RDF database, all orchestrated via Docker Compose

```bash
docker compose up --build
```

## 4. Stop the System

To stop all running services:

```bash
docker compose down
```

## 5. Example API Usage

### DPO use-case workflow (GDPR Article 30)

The prototype supports an isolated named graph for each use case. This is the
recommended starting point for the controller/ROPA scenario: a DPO first
creates the domain data, then requests an assessment, then retrieves its latest
stored status. The input service records a `ComplianceEvent` in the use-case
graph and the compliance service stores the assessment outcome in a dedicated
assessment graph.

#### 1. Create the use case from form-ready JSON

```bash
curl -X POST http://localhost:8000/use-cases \
  -H 'Content-Type: application/json' \
  -d '{
    "label": "Customer support processing",
    "controller_name": "Example Ltd",
    "controller_contact": "dpo@example.com",
    "processing_activity": "Respond to customer support requests",
    "ropa_present": false
  }'
```

The response includes `use_case_id`, a graph URI, and the available
assessment: GDPR Article 30. A client may supply its own stable `use_case_id`
(letters, numbers, `_`, and `-` only) when it needs to update or refer to an
external record.

#### 2. Run an article-level compliance assessment

```bash
curl -X POST 'http://localhost:8001/check?use_case_id=<use_case_id>&law=GDPR&article=30'
```

The response contains an overall `passed`/`failed` status and DPO-facing
findings: requirement IDs where available, messages, severity, and affected
resources. The current prototype maps GDPR Articles 30 and 32 to their SHACL
files; unsupported article values receive `400`.

#### 3. Retrieve the latest assessment status

```bash
curl 'http://localhost:8002/status?use_case_id=<use_case_id>&law=GDPR&article=30'
```

Status is keyed by use case, law, and article. It returns `not_found` when no
assessment has been run, rather than silently selecting a result for a
different law or article.

`POST /input` and `POST /validate` remain available for older RDF-upload
clients. New integrations should use `/use-cases` and `/check`.

#### Input API (http://localhost:8000): POST – Submit RDF data

Used to send RDF data to the system and store it in Fuseki.

```curl
curl -X POST "http://localhost:8000/input" \
  -H "Content-Type: text/turtle" \
  --data-binary @data.ttl
```
Expected Response
```json
{
  "message": "RDF data successfully uploaded",
  "status": "SUCCESS"
}
```
#### Compliance API (http://localhost:8001) : POST – Run SHACL validation

Used to validate RDF data against compliance rules.
```curl
curl -X POST "http://localhost:8001/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "default"
  }'
```

Expected Response
```json
{
  "compliance_status": "NON-COMPLIANT",
  "alerts": [
    "Controller missing DPO",
    "Controller missing ROPA"
  ],
  "report": {
    "total_checks": 5,
    "passed": 3,
    "failed": 2
  }
}
```

#### Status API (http://localhost:8002) : GET – System status overview

Used to check system health and latest compliance state.
```curl
curl -X GET "http://localhost:8002/status"
```

Expected Response
```json
{
  "system": "RECITALS",
  "fuseki_status": "RUNNING",
  "last_validation": "2026-06-11T10:15:00Z",
  "overall_compliance": "NON-COMPLIANT"
}
```
