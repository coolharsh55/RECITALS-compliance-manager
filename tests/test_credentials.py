"""Fuseki credentials come from the environment, never from the code."""
import importlib.util
import re
import subprocess
import sys

import pytest

from conftest import ROOT, TEST_PASSWORD, TEST_USER

SERVICES = ("input-api", "compliance-api", "status-api")


def test_apis_log_in_with_configured_credentials(services, fuseki):
    """APIs log in with configured credentials."""
    services["input-api"].post("/use-cases", data={"use_case_id": "UC1", "law": "GDPR", "label": "x"})
    services["input-api"].post("/input", data={"use_case_id": "UC1"},
                               files={"file": ("d.ttl", b"<http://e/x> <http://e/p> 1 .", "text/turtle")})
    services["compliance-api"].post("/check", data={"use_case": "UC1", "law": "GDPR", "article": 30})
    services["status-api"].get("/status", params={"use_case_id": "UC1"})
    assert fuseki.auth_seen == {(TEST_USER, TEST_PASSWORD)}


@pytest.mark.parametrize("service", SERVICES)
def test_api_refuses_to_start_without_credentials(service):
    """API refuses to start without credentials."""
    env = {"PATH": "", "PYTHONPATH": ":".join(sys.path)}
    code = (f"import importlib.util as u; s=u.spec_from_file_location('m', {str(ROOT / service / 'main.py')!r}); "
            "u.module_from_spec(s); s.loader.exec_module(u.module_from_spec(s))")
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "FUSEKI_USER and FUSEKI_PASSWORD must be set" in result.stderr


@pytest.mark.parametrize("service", SERVICES)
def test_no_password_in_code(service):
    """No Fuseki password is hard-coded in the service."""
    source = (ROOT / service / "main.py").read_text()
    assert not re.search(r"""["']admin["']""", source)


def test_compose_takes_credentials_from_env_and_keeps_fuseki_local():
    """docker-compose takes the credentials from .env and publishes Fuseki on 127.0.0.1 only."""
    text = (ROOT / "docker-compose.yml").read_text()
    assert "admin" not in text
    assert '- "127.0.0.1:3030:3030"' in text and '"3030:3030"' not in text
    for port in ("8000", "8001", "8002"):
        assert f'- "127.0.0.1:{port}:8000"' in text and f'- "{port}:8000"' not in text
    assert "FUSEKI_USER: ${FUSEKI_USER:?" in text and "FUSEKI_PASSWORD: ${FUSEKI_PASSWORD:?" in text
    # every API service gets the shared credentials block
    for service in SERVICES:
        block = text.split(f"  {service}:")[1].split("\n  depends_on")[0]
        assert "<<: *fuseki-credentials" in block, service


def test_env_file_is_ignored_and_example_has_no_real_password():
    """.env is ignored by git and .env.example has no real password."""
    assert ".env" in (ROOT / ".gitignore").read_text().split()
    example = (ROOT / ".env.example").read_text()
    assert "FUSEKI_PASSWORD=change-me" in example
