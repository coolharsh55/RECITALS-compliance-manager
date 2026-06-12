# RECITALS-compliance-manager

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
