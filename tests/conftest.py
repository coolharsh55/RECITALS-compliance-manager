"""Test helpers: an in-memory stand-in for Fuseki so the APIs run without Docker."""
import importlib.util
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from rdflib import Dataset, Graph, URIRef

ROOT = Path(__file__).resolve().parent.parent

# The APIs refuse to start without Fuseki credentials.
TEST_USER, TEST_PASSWORD = "test-user", "test-secret"
os.environ.setdefault("FUSEKI_USER", TEST_USER)
os.environ.setdefault("FUSEKI_PASSWORD", TEST_PASSWORD)


class FakeResponse:
    """Minimal stand-in for a requests.Response."""
    def __init__(self, status_code=200, text="", payload=None):
        self.status_code = status_code
        self.text = text if payload is None else json.dumps(payload)
        self._payload = payload

    def json(self):
        """Return the JSON payload, like requests.Response.json()."""
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeFuseki:
    """Mimics /dataset/data, /dataset/query and /dataset/update (no union default graph)."""

    def __init__(self):
        self.ds = Dataset()
        self.auth_seen = set()

    def post(self, url, data=None, headers=None, params=None, auth=None, **_):
        """Answer a POST the way Fuseki's /data, /update and /query endpoints would."""
        self.auth_seen.add(auth)
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        if url.endswith("/data"):
            graph_name = (params or {}).get("graph")
            target = self.ds.graph(URIRef(graph_name)) if graph_name else self.ds.default_graph
            target.parse(data=data, format="turtle")
            return FakeResponse(201)
        if url.endswith("/update"):
            self.ds.update(data)
            return FakeResponse(204)
        if url.endswith("/query"):
            try:
                result = self.ds.query(data)
            except Exception as exc:  # malformed SPARQL -> Fuseki returns 400
                return FakeResponse(400, text=str(exc))
            if result.type == "CONSTRUCT":
                return FakeResponse(200, text=result.graph.serialize(format="turtle"))
            return FakeResponse(200, payload=json.loads(result.serialize(format="json")))
        return FakeResponse(404)


def load_service(name):
    """Import a service's main.py as a module."""
    path = ROOT / name / "main.py"
    spec = importlib.util.spec_from_file_location(f"{name.replace('-', '_')}_main", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fuseki():
    """An empty in-memory Fuseki for one test."""
    return FakeFuseki()


@pytest.fixture
def services(fuseki, monkeypatch):
    """Test clients for the three APIs, all talking to the in-memory Fuseki."""
    clients = {}
    for name in ("input-api", "compliance-api", "status-api"):
        module = load_service(name)
        monkeypatch.setattr(module.requests, "post", fuseki.post)
        clients[name] = TestClient(module.app)
    # compliance-api loads shape files relative to its working directory
    monkeypatch.chdir(ROOT / "compliance-api")
    return clients
