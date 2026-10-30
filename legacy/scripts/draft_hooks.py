"""Ask the model server to DRAFT memory hooks (shape, mnemonic, example word, picture) for lesson cards.

Drafts never go straight to learners: they are written to data/<pair>/drafts/<unit>.json with
status "draft_unverified". A native speaker reviews them, then copies the good ones into the unit file.

    export GEMINI_API_KEY=<key>          # Gemma 4 on Google AI Studio (or SETU_LLM_URL=<your vLLM server>/v1)
    python scripts/draft_hooks.py L0-07            # draft hooks for every card of unit L0-07
    python scripts/draft_hooks.py L0-07 --dry-run  # just print the prompt
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from setu.contracts import Unit  # noqa: E402
from setu.llm import llm_from_env  # noqa: E402

PROMPT = """You help Hindi speakers learn the Telugu script. For the Telugu letter "{te}" (it sounds like Hindi "{hi}"),
write memory hooks in simple Hindi (Devanagari). Reply with JSON only:
{{"shape": "<what the letter looks like, so it can be pictured; one short line>",
  "mnemonic": "<a tiny vivid story linking that shape to the sound {hi}; one short line>",
  "example": "<one common Telugu word starting with {te} that a Hindi speaker knows, written 'TELUGU = HINDI'>",
  "picture": "<one emoji for that word>"}}
Do not invent words. If unsure about the example word, leave it empty."""


def ask(prompt: str) -> dict:
    llm = llm_from_env()
    llm.timeout = max(llm.timeout, 60)
    text = llm.chat("You write careful teaching material. Reply with JSON only.", prompt, max_tokens=400, temperature=0.4)
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def draft_unit(unit: Unit, asker=ask) -> dict:
    cards = []
    for line in unit.lesson:
        try:
            hooks = asker(PROMPT.format(te=line.telugu, hi=line.hindi))
        except Exception as e:                                   # keep going; a reviewer sees the error
            hooks = {"error": f"{type(e).__name__}: {e}"}
        cards.append({"hindi": line.hindi, "telugu": line.telugu, **{k: hooks.get(k, "") for k in
                      ("shape", "mnemonic", "example", "picture", "error") if k in hooks or k != "error"}})
    return {"unit_id": unit.unit_id, "status": "draft_unverified", "drafted_by": getattr(llm_from_env(), "name", ""),
            "cards": cards}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("unit_id"); ap.add_argument("--pair", default="hi-te"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    unit = Unit.model_validate(json.loads((ROOT / "data" / a.pair / f"{a.unit_id}.json").read_text(encoding="utf-8")))
    if a.dry_run:
        print(PROMPT.format(te=unit.lesson[0].telugu, hi=unit.lesson[0].hindi)); return
    if llm_from_env() is None:
        sys.exit("Set GEMINI_API_KEY (Google AI Studio) or SETU_LLM_URL (your model server) first.")
    out = ROOT / "data" / a.pair / "drafts" / f"{a.unit_id}.json"
    if out.exists():
        sys.exit(f"{out} exists; review or delete it first (drafts are never overwritten).")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(draft_unit(unit), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Draft written: {out}  (status draft_unverified — a native speaker must review it)")


if __name__ == "__main__":
    main()
