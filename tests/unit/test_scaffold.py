"""Slice 1.1: the new package skeleton exists and the app answers a health check.

Spec IDs: E-09, X-RULES-02.
"""
import importlib

from fastapi.testclient import TestClient

SUBPACKAGES = ["domain", "content", "agents", "store", "web", "research", "export", "speech", "memory"]


def test_every_subpackage_imports():
    for name in SUBPACKAGES:
        importlib.import_module(f"setu.{name}")


def test_domain_has_no_io_dependencies():
    # setu.domain is the deterministic core: no web, database, network or agent imports.
    import re
    from pathlib import Path

    forbidden = re.compile(
        r"^\s*(from|import)\s+(fastapi|starlette|sqlalchemy|httpx|requests|urllib|setu\.(web|store|agents|speech))\b",
        re.MULTILINE,
    )
    root = Path(__file__).resolve().parents[2] / "setu" / "domain"
    offenders = [p.name for p in root.rglob("*.py") if forbidden.search(p.read_text(encoding="utf-8"))]
    assert offenders == []


def test_healthz_reports_ok_and_version():
    from setu.web.app import create_app

    client = TestClient(create_app())
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_runtime_has_no_commercial_model_client():
    # ADR-0003: no Gemini / Google AI Studio client in the new runtime package.
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "setu"
    text = "\n".join(p.read_text(encoding="utf-8") for p in root.rglob("*.py"))
    for marker in ("generativelanguage.googleapis.com", "GEMINI_API_KEY", "GeminiAPI"):
        assert marker not in text
