"""Self-hosted model client (P-MODEL-01, P-COST-04, ADR on self-hosting). Provider-independent.

Speaks the OpenAI-compatible chat-completions protocol, so it works with LM Studio, Ollama, vLLM or llama.cpp
servers. Configuration comes only from the environment (no secrets in source):

    SETU_LLM_URL      e.g. http://localhost:1234/v1   (unset: no model; every agent uses its approved fallback)
    SETU_LLM_MODEL    e.g. qwen/qwen3.5-9b
    SETU_LLM_TIMEOUT  seconds, default 20
    SETU_LLM_RETRIES  default 1

Only local endpoints are accepted (localhost, 127.0.0.1, private network or `.local` hosts), so learner data never
reaches a commercial API by misconfiguration. Every call returns a `Completion` with the text, latency, token usage
and error, which the caller logs to `model_call`. `MockProvider` exists for tests only and says so in its name.
"""
import dataclasses
import hashlib
import ipaddress
import json
import os
import re
import time
from collections.abc import Callable
from urllib.parse import urlparse

import httpx

PROMPT_VERSION = "agents-1"
_JSON = re.compile(r"\{.*\}", re.DOTALL)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


class NotLocal(ValueError):
    """The configured endpoint is not a self-hosted (local or private-network) server."""


@dataclasses.dataclass(frozen=True)
class Completion:
    text: str | None
    model: str
    latency_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    error: str | None = None
    request_hash: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None and self.text is not None


def is_local(url: str) -> bool:
    host = urlparse(url).hostname or ""
    if host == "localhost" or host.endswith((".local", ".internal")):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def request_hash(messages) -> str:
    return hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class OpenAICompatible:
    """A self-hosted OpenAI-compatible chat endpoint."""

    def __init__(self, base_url: str, model: str, *, timeout: float = 20.0, retries: int = 1,
                 transport: httpx.BaseTransport | None = None):
        if not is_local(base_url):
            raise NotLocal(f"{base_url} is not a local or private-network endpoint")
        self.base_url, self.model, self.timeout, self.retries = base_url.rstrip("/"), model, timeout, retries
        self._client = httpx.Client(timeout=timeout, transport=transport)

    @classmethod
    def from_environment(cls) -> "OpenAICompatible | None":
        url = os.environ.get("SETU_LLM_URL")
        if not url:
            return None
        return cls(url, os.environ.get("SETU_LLM_MODEL", "local-model"),
                   timeout=float(os.environ.get("SETU_LLM_TIMEOUT", "20")),
                   retries=int(os.environ.get("SETU_LLM_RETRIES", "1")))

    def complete(self, messages, *, max_tokens: int = 200, temperature: float = 0.4) -> Completion:
        body = {"model": self.model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        h, error = request_hash(messages), None
        start = time.monotonic()
        for _ in range(self.retries + 1):
            try:
                r = self._client.post(f"{self.base_url}/chat/completions", json=body)
                r.raise_for_status()
                data = r.json()
                text = _THINK.sub("", data["choices"][0]["message"]["content"] or "").strip()
                usage = data.get("usage") or {}
                return Completion(text, data.get("model", self.model), int((time.monotonic() - start) * 1000),
                                  usage.get("prompt_tokens"), usage.get("completion_tokens"), None, h)
            except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as e:
                error = f"{type(e).__name__}: {e}"[:300]
        return Completion(None, self.model, int((time.monotonic() - start) * 1000), error=error, request_hash=h)


class MockProvider:
    """FOR TESTS ONLY. Returns scripted replies; it is not a language model and is never used in the app."""

    model = "mock-for-tests"

    def __init__(self, replies: list[str] | Callable[[list], str]):
        self._replies = replies
        self.calls: list = []

    def complete(self, messages, **_) -> Completion:
        self.calls.append(messages)
        text = self._replies(messages) if callable(self._replies) else self._replies.pop(0)
        return Completion(text, self.model, 0, None, None, None, request_hash(messages))


def parse_json(text: str | None, required: tuple) -> dict | None:
    """Structured-output validation: the first JSON object in the reply, with every required key, or None."""
    if not text:
        return None
    m = _JSON.search(text)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except ValueError:
        return None
    return obj if isinstance(obj, dict) and all(k in obj for k in required) else None
