"""Capture screenshots of the running demo with headless Chrome (DevTools protocol). Development only.

    python -m scripts.screenshots <learner-handle> <passphrase> [out_dir]

Logs in through the real login form, advances the same learner over HTTP where a state is needed (Raju's planted
turn, a coach hint, an open scene), and captures each page at desktop (1280×900) and mobile (390×844) widths.
"""
import asyncio
import base64
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import websockets
from sqlalchemy import create_engine, text

BASE = "http://127.0.0.1:8000"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEMO_DB = "postgresql+psycopg://setu_migrate:setu-dev-only@localhost:5433/setu_demo"
ANS = {"तुम आ रहे हो क्या": "నువ్వు వస్తావా", "यह किताब है क्या": "ఇది పుస్తకమా", "मैं नहीं जाऊँगा": "నేను వెళ్ళను",
       "वह नहीं आएगा": "అతను రాడు", "यह घर है": "ఇది ఇల్లు", "वह पेड़ है": "అది చెట్టు"}


class Chrome:
    def __init__(self, port=9333):
        self.port, self.n = port, 0
        self.proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={port}",
                                      f"--user-data-dir={tempfile.mkdtemp()}", "--no-first-run", "--hide-scrollbars",
                                      "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                targets = httpx.get(f"http://127.0.0.1:{port}/json").json()
                self.ws_url = next(t["webSocketDebuggerUrl"] for t in targets if t["type"] == "page")
                return
            except (httpx.HTTPError, StopIteration, ValueError):
                time.sleep(0.2)
        raise RuntimeError("Chrome did not start")

    async def __aenter__(self):
        self.ws = await websockets.connect(self.ws_url, max_size=50_000_000)
        await self.cmd("Page.enable")
        return self

    async def __aexit__(self, *exc):
        await self.ws.close()
        self.proc.terminate()

    async def cmd(self, method, **params):
        self.n += 1
        await self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == self.n:
                return msg.get("result", {})

    async def go(self, url):
        await self.cmd("Page.navigate", url=url)
        await asyncio.sleep(1.2)

    async def js(self, expr):
        return await self.cmd("Runtime.evaluate", expression=expr, awaitPromise=True)

    async def shot(self, path: Path, width, height, mobile=False):
        await self.cmd("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=2,
                       mobile=mobile)
        await asyncio.sleep(0.4)
        r = await self.cmd("Page.captureScreenshot", format="png", captureBeyondViewport=False)
        path.write_bytes(base64.b64decode(r["data"]))


def http_learner(handle, pw):
    c = httpx.Client(base_url=BASE, follow_redirects=True)
    c.post("/login", data={"handle": handle, "passphrase": pw})
    return c


def eid(p):
    return re.search(r'name="exchange_id" value="([^"]+)"', p).group(1)


def to_planted(c):
    page = c.get("/learn/rules").text
    for _ in range(25):
        if "राजू ने लिखा" in page:
            return page
        if "/learn/rules/continue" in page:
            c.post("/learn/rules/continue", data={"exchange_id": eid(page)})
        else:
            m = next((m for m in ANS if m in page), None)
            if m:
                n = (re.search(r'name="n" value="(\d+)"', page) or [None, "1"])[1]
                c.post("/learn/rules/answer", data={"exchange_id": eid(page), "n": n, "typed": ANS[m]})
        page = c.get("/learn/rules").text
    raise RuntimeError("Raju never planted an error")


def place_everything(c, handle):
    """Pass the placement check with the right answers (read from the demo database) so the scenes open."""
    engine = create_engine(DEMO_DB)
    c.post("/learn/placement/start")
    for _ in range(40):
        page = c.get("/learn/placement").text
        if "/learn/placement/answer" not in page:
            return
        with engine.connect() as x:
            task = x.execute(text("SELECT e.task FROM exchange e JOIN session s ON s.id = e.session_id JOIN learner l "
                                  "ON l.id = s.learner_id LEFT JOIN attempt a ON a.exchange_id = e.id WHERE l.handle = "
                                  ":h AND s.mode = 'diagnostic' AND a.id IS NULL ORDER BY e.created_at DESC LIMIT 1"),
                             {"h": handle}).scalar()
        c.post("/learn/placement/answer", data={"exchange_id": eid(page), "typed": task["expected"]})


async def main(handle, pw, out):
    out.mkdir(parents=True, exist_ok=True)
    h = http_learner(handle, pw)
    async with Chrome() as ch:
        await ch.go(f"{BASE}/login")
        await ch.js(f"document.querySelector('[name=handle]').value={json.dumps(handle)};"
                    f"document.querySelector('[name=passphrase]').value={json.dumps(pw)};"
                    "document.querySelector('form[action=\"/login\"]').submit();")
        await asyncio.sleep(1.5)

        async def both(name, url):
            await ch.go(url)
            await ch.shot(out / f"{name}-desktop.png", 1280, 900)
            await ch.go(url)
            await ch.shot(out / f"{name}-mobile.png", 390, 844, mobile=True)

        await both("01-home", f"{BASE}/")
        await both("02-lesson-letter", f"{BASE}/learn/letters")
        page = to_planted(h)
        await both("03-raju", f"{BASE}/learn/rules")
        wrong = re.search(r'class="letter-big"><span lang="te">([^<]+)</span>', page).group(1)
        h.post("/learn/rules/answer", data={"exchange_id": eid(page), "n": "1", "typed": wrong})
        await both("04-coach-hint", f"{BASE}/learn/rules")
        place_everything(h, handle)
        await both("05-progress", f"{BASE}/ladder")
        h.post("/learn/scenes/hi-te-scene-01/start")
        await both("06-friend-scene", f"{BASE}/learn/scenes/hi-te-scene-01")
        await both("07-home-after", f"{BASE}/")
    print(sorted(p.name for p in out.glob("*.png")))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2], Path(sys.argv[3] if len(sys.argv) > 3 else "docs/submission/screenshots")))
