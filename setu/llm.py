"""One small client for the language model. Standard library only (no extra packages).

Two ways to reach Gemma, both chosen only by environment variables:

  1. Google AI Studio (Gemini API), no GPU needed. Gemma 4 is served there (Gemma 3 was removed in May 2026).
         GEMINI_API_KEY=<key from aistudio.google.com>         (or SETU_GEMINI_API_KEY)
         SETU_LLM_MODEL=gemma-4-26b-a4b-it                      (default; or gemma-4-31b-it)
  2. Your own OpenAI-compatible server, e.g. vLLM serving Gemma on a GPU box:
         SETU_LLM_URL=https://<gpu-box>/v1   SETU_LLM_MODEL=google/gemma-3-12b-it   SETU_LLM_API_KEY=<secret>

  SETU_LLM_TIMEOUT  seconds per call (default 12). If both are set, SETU_LLM_URL wins.
  SETU_GEMINI_URL   only to point at a proxy or a test server (default: Google's generateContent URL).
Nothing set = no model: the app uses fixed sentences and still works.

Pictures for letter cards come from Google's image models with the same GEMINI_API_KEY (see GeminiImages);
SETU_IMAGES=off turns them off.
"""
from __future__ import annotations
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_DEFAULT = "gemma-4-26b-a4b-it"
OPENAI_DEFAULT = "google/gemma-3-12b-it"


def _ssl_context() -> ssl.SSLContext:
    """Python from python.org on a Mac ships without the list of trusted certificates, so every https call
    fails with URLError (CERTIFICATE_VERIFY_FAILED). certifi (installed with streamlit) carries that list."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


_SSL = _ssl_context()


def _post(url: str, body: dict, headers: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as r:
        return json.loads(r.read().decode())


def _http_message(e) -> str:
    """The error message Google/the server sent back (read once and kept, the body can only be read once)."""
    if not hasattr(e, "_setu_msg"):
        try:
            e._setu_msg = json.loads(e.read().decode()).get("error", {}).get("message", "") or str(e.reason)
        except Exception:
            e._setu_msg = str(getattr(e, "reason", ""))
    return e._setu_msg


def _is_auth_error(code: int, msg: str) -> bool:
    m = msg.lower()
    return code in (400, 401, 403) and any(k in m for k in ("api key", "api_key", "access_token", "unauthenticated",
                                                            "credential", "permission"))


def describe_error(e: Exception) -> str:
    """A short, readable reason, e.g. 'URLError: CERTIFICATE_VERIFY_FAILED' or 'HTTPError 400: API key not valid'."""
    if isinstance(e, urllib.error.HTTPError):
        return f"HTTPError {e.code}: {_http_message(e)}"[:200]
    reason = getattr(e, "reason", None) or e
    return f"{type(e).__name__}: {reason}"[:200]


AUTH_MODES = ("header", "query", "bearer")
# How much of the request to send, from full to plain. Some models answer 400/500 to settings they don't support.
VARIANTS = ("full", "no-thinking", "plain")      # plain: no thinking setting, system text folded into the message
ATTEMPTS = [(m, v) for m in ("header", "query") for v in VARIANTS] + [("bearer", "plain")]


class GeminiAPI:
    """Gemma on Google AI Studio.
    Google's newer keys (starting 'AQ.') are accepted by some ways of sending the key and refused by others, and
    some request settings make the server fail. So the first call tries, in order:
        header  native generateContent, key in the x-goog-api-key header      x  full / no-thinking / plain
        query   native generateContent, key in the link (?key=...)            x  full / no-thinking / plain
        bearer  Google's OpenAI-compatible endpoint, 'Authorization: Bearer'
    and keeps the first combination that works. `attempts` records what happened, for the sidebar check.
    Thinking is turned off when the model allows it, so Raju answers quickly and the reply is only his line."""

    def __init__(self, api_key: str, model: str = GEMINI_DEFAULT, timeout: float = 12, endpoint: str = GEMINI_URL):
        self.api_key, self.model, self.timeout, self.endpoint = api_key, model, timeout, endpoint
        self.name = f"{model} (Google AI Studio)"
        self.auth = None                                  # (mode, variant) that worked
        self.attempts = []                                # [(mode, variant, "ok" | error)] of the last search

    def chat(self, system: str, user: str, max_tokens: int = 80, temperature: float = 0.9,
             timeout: Optional[float] = None) -> str:
        if timeout is not None:                           # a slow job (e.g. drawing) may wait longer
            old, self.timeout = self.timeout, timeout
            try:
                return self.chat(system, user, max_tokens, temperature)
            finally:
                self.timeout = old
        if self.auth:
            try:
                return self._call(*self.auth, system, user, max_tokens, temperature)
            except urllib.error.HTTPError as e:           # Google's occasional "500 Internal error": try once more
                if e.code >= 500:
                    return self._call(*self.auth, system, user, max_tokens, temperature)
                raise
        self.attempts, last, refused = [], None, set()
        for mode, variant in ATTEMPTS:
            if mode in refused:
                continue
            try:
                text = self._call(mode, variant, system, user, max_tokens, temperature)
            except urllib.error.HTTPError as e:
                msg = _http_message(e)
                self.attempts.append((mode, variant, f"{e.code}: {msg}"[:120]))
                last = e
                if _is_auth_error(e.code, msg):
                    refused.add(mode)                     # key refused this way: skip its other variants
                elif e.code in (404, 429):                # wrong model name / rate limit: trying more won't help
                    raise
                continue
            self.attempts.append((mode, variant, "ok"))
            self.auth = (mode, variant)
            return text
        raise last

    def see(self, image: bytes, mime: str, question: str, max_tokens: int = 20) -> str:
        """Ask Gemma about a picture (Gemma 4 can see images). Used to check AI pictures for stray writing."""
        import base64
        b64 = base64.b64encode(image).decode()
        modes = [self.auth[0]] if self.auth else ["header", "query", "bearer"]
        last = None
        for mode in modes:
            try:
                if mode == "bearer":
                    url = self.endpoint.split("/models/")[0] + "/openai/chat/completions"
                    body = {"model": self.model, "max_tokens": max_tokens, "temperature": 0,
                            "messages": [{"role": "user", "content": [
                                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                                {"type": "text", "text": question}]}]}
                    out = _post(url, body, {"Authorization": f"Bearer {self.api_key}"}, max(self.timeout, 30))
                    return (out["choices"][0]["message"]["content"] or "").strip()
                body = {"contents": [{"role": "user", "parts": [{"inlineData": {"mimeType": mime, "data": b64}},
                                                                {"text": question}]}],
                        "generationConfig": {"temperature": 0, "maxOutputTokens": max_tokens}}
                out = _post_kw(_native(self.endpoint, self.model, self.api_key, mode), body, max(self.timeout, 30))
                return "".join(p.get("text", "") for p in out["candidates"][0]["content"]["parts"] if not p.get("thought")).strip()
            except urllib.error.HTTPError as e:
                last = e
                if not _is_auth_error(e.code, _http_message(e)):
                    raise
        raise last

    def _call(self, mode: str, variant: str, system: str, user: str, max_tokens: int, temperature: float) -> str:
        if mode == "bearer":
            url = self.endpoint.split("/models/")[0] + "/openai/chat/completions"
            body = {"model": self.model, "max_tokens": max_tokens, "temperature": temperature,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
            out = _post(url, body, {"Authorization": f"Bearer {self.api_key}"}, self.timeout)
            return (out["choices"][0]["message"]["content"] or "").strip()
        cfg = {"temperature": temperature, "maxOutputTokens": max_tokens}
        if variant == "full":
            cfg["thinkingConfig"] = {"thinkingLevel": "minimal"}
        body = {"generationConfig": cfg}
        if variant == "plain":
            body["contents"] = [{"role": "user", "parts": [{"text": system + "\n\n" + user}]}]
        else:
            body["systemInstruction"] = {"parts": [{"text": system}]}
            body["contents"] = [{"role": "user", "parts": [{"text": user}]}]
        url = self.endpoint.format(model=self.model)
        headers = {"x-goog-api-key": self.api_key} if mode == "header" else {}
        if mode == "query":
            url += "?key=" + urllib.parse.quote(self.api_key, safe="")
        out = _post(url, body, headers, self.timeout)
        parts = out["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()


def _native(endpoint: str, model: str, key: str, mode: str):
    """(url, headers) for Google's native endpoint, with the key sent the given way."""
    url = endpoint.format(model=model)
    if mode == "query":
        return url + "?key=" + urllib.parse.quote(key, safe=""), {}
    return url, {"x-goog-api-key": key}


def _post_kw(url_headers, body, timeout):
    url, headers = url_headers
    return _post(url, body, headers, timeout)


IMAGE_MODELS = "gemini-3.1-flash-lite-image,gemini-3.1-flash-image,gemini-nano-banana-2.1,gemini-2.5-flash-image"


class GeminiImages:
    """Pictures from Google's image models ('Nano Banana'), with the same key as Gemma.
    SETU_IMAGE_MODEL may list several models, comma-separated; the first that works with your key is kept
    (some have no free tier, older ones are being retired)."""

    def __init__(self, api_key: str, models: str = IMAGE_MODELS, timeout: float = 90, endpoint: str = GEMINI_URL):
        self.api_key, self.timeout, self.endpoint = api_key, timeout, endpoint
        self.models = [m.strip() for m in models.split(",") if m.strip()]
        self.model = None                                 # the one that worked
        self.mode = None
        self.attempts = []

    def draw(self, prompt: str):
        """Returns (image bytes, mime type). Raises the last error if no model works."""
        import base64
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}}
        combos = [(self.model, self.mode)] if self.model else [(m, md) for m in self.models for md in ("header", "query")]
        self.attempts, last, refused = [], None, set()
        for model, mode in combos:
            if (model, mode) in refused:
                continue
            try:
                url, headers = _native(self.endpoint, model, self.api_key, mode)
                out = _post(url, body, headers, self.timeout)
            except urllib.error.HTTPError as e:
                msg = _http_message(e)
                self.attempts.append((model, mode, f"{e.code}: {msg}"[:120]))
                last = e
                if e.code in (400, 401, 403) and _is_auth_error(e.code, msg):
                    continue                              # key refused this way: try the other way / next model
                refused.update({(model, "header"), (model, "query")})   # this model doesn't work for us: next model
                continue
            for part in out.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                data = part.get("inlineData") or part.get("inline_data")
                if data and data.get("data"):
                    self.model, self.mode = model, mode
                    self.attempts.append((model, mode, "ok"))
                    return base64.b64decode(data["data"]), data.get("mimeType") or data.get("mime_type") or "image/png"
            self.attempts.append((model, mode, "no picture in the reply"))
            refused.update({(model, "header"), (model, "query")})
        if last is not None:
            raise last
        raise RuntimeError("no image model returned a picture")


def images_from_env() -> Optional[GeminiImages]:
    """Pictures need a Google AI Studio key (GEMINI_API_KEY). None = no AI pictures (the emoji is shown)."""
    key = (os.environ.get("SETU_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip().strip('"\'<> ')
    if not key or os.environ.get("SETU_IMAGES", "on").lower() in ("0", "off", "no"):
        return None
    return GeminiImages(key, os.environ.get("SETU_IMAGE_MODEL", IMAGE_MODELS),
                        endpoint=os.environ.get("SETU_GEMINI_URL", GEMINI_URL))


class OpenAICompatible:
    """Any OpenAI-style /chat/completions server (vLLM, Ollama, ...)."""

    def __init__(self, base_url: str, model: str = OPENAI_DEFAULT, api_key: str = "", timeout: float = 12):
        self.base_url, self.model, self.api_key, self.timeout = base_url.rstrip("/"), model, api_key, timeout
        self.name = model

    def chat(self, system: str, user: str, max_tokens: int = 80, temperature: float = 0.9,
             timeout: Optional[float] = None) -> str:
        body = {"model": self.model, "temperature": temperature, "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        out = _post(self.base_url + "/chat/completions", body, headers, timeout or self.timeout)
        return (out["choices"][0]["message"]["content"] or "").strip()


def llm_from_env():
    """The configured model, or None (fixed sentences)."""
    timeout = float(os.environ.get("SETU_LLM_TIMEOUT", "20"))
    url = os.environ.get("SETU_LLM_URL", "").strip()
    if url:
        return OpenAICompatible(url, os.environ.get("SETU_LLM_MODEL", OPENAI_DEFAULT),
                                os.environ.get("SETU_LLM_API_KEY", ""), timeout)
    key = (os.environ.get("SETU_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip().strip('"\'<> ')
    if key:
        return GeminiAPI(key, os.environ.get("SETU_LLM_MODEL", GEMINI_DEFAULT), timeout,
                         os.environ.get("SETU_GEMINI_URL", GEMINI_URL))
    return None


def clean_line(text: str) -> str:
    """Models sometimes wrap the line in quotes or add 'Raju:'. Keep only the first line, without those."""
    line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    for pre in ("Raju:", "राजू:", "Raju :", "**Raju:**"):
        if line.startswith(pre):
            line = line[len(pre):]
    return line.strip().strip('"“”\'*').strip()
