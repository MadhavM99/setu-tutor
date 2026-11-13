"""Copy fidelity before QLoRA (TASKS.md task 10): can the base model repeat a Telugu sentence exactly? The fine-tuning
task is "copy this correct sentence with one planted edit", so faithful copying is what it needs.

20 correct Telugu sentences from the bank (chunks, scene lines, TE->HI meanings), none from the frozen planting cases
and none a near-duplicate of one. Each model gets "Repeat this sentence exactly" (greedy, its chat template).
Reports exact-match rate (after `normalise.canonical`) and character edit distance.

    PYTHONPATH=. /tmp/ftvenv/bin/python scripts/ft_copy_check.py --device cpu     # -> reports/ft_copy_check.json
In Colab the notebook's first cell runs the same `run()`.
"""
import argparse
import json
import re
import time
from pathlib import Path

import yaml

from setu.domain.normalise import canonical

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/ft_copy_check.json"
MODELS = {"Gemma-3-1B-it": "unsloth/gemma-3-1b-it", "Qwen2.5-1.5B-Instruct": "Qwen/Qwen2.5-1.5B-Instruct"}
INSTRUCTION = "Repeat this Telugu sentence exactly, character for character. Write only the sentence.\n\n"
N = 20
_TEL = re.compile(r"^[ఀ-౿]+(?: [ఀ-౿]+)*[?!.]?$")


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def norm_distance(a: str, b: str) -> float:
    a, b = canonical(a), canonical(b)
    return levenshtein(a, b) / max(1, len(a), len(b))


def frozen_sentences() -> list[str]:
    m = json.loads((ROOT / "tests/eval_sets/manifest.json").read_text(encoding="utf-8"))
    return [s for c in m["planting_cases"] for s in (c["correct_form"], c["wrong_form"])]


def sentences(n: int = N, near: float = 0.3) -> list[str]:
    """Deterministic: bank order, at least 2 words, Telugu only, not within `near` of any frozen sentence."""
    cands = []
    for e in yaml.safe_load((ROOT / "content/hi-te/chunks.yaml").read_text(encoding="utf-8")):
        cands.append(e.get("telugu") or "")
    for s in yaml.safe_load((ROOT / "content/hi-te/scene_scripts.yaml").read_text(encoding="utf-8")):
        cands += [ln.get("telugu") or "" for ln in s.get("lines", [])]
    for p in sorted((ROOT / "content/te-hi/rules").glob("*.yaml")):
        cands += [it.get("l1_meaning") or "" for it in yaml.safe_load(p.read_text(encoding="utf-8"))["items"]]
    frozen = frozen_sentences()
    out = []
    for s in dict.fromkeys(c.strip() for c in cands):
        if len(s.split()) >= 2 and _TEL.match(s) and all(norm_distance(s, f) > near for f in frozen):
            out.append(s)
    return out[:n]


def score(ref: str, out: str) -> dict:
    first = (out or "").strip().splitlines()[0].strip().strip('"“”') if (out or "").strip() else ""
    return {"ref": ref, "output": out, "first_line": first, "exact": canonical(first) == canonical(ref),
            "char_edit_distance": levenshtein(canonical(first), canonical(ref)),
            "norm_edit_distance": round(norm_distance(first, ref), 3)}


def run(model_id: str, device: str = "auto", sents=None) -> dict:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    sents = sents or sentences()
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(model_id, dtype=torch.float32).to(device).eval()
    t0, rows = time.monotonic(), []
    for s in sents:
        enc = tok.apply_chat_template([{"role": "user", "content": INSTRUCTION + s}], add_generation_prompt=True,
                                      return_tensors="pt", return_dict=True)
        enc = {k: v.to(device) for k, v in enc.items()}
        n_ref = len(tok.encode(s, add_special_tokens=False))
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=n_ref + 12, do_sample=False,
                                 pad_token_id=tok.pad_token_id or tok.eos_token_id)
        rows.append(score(s, tok.decode(out[0, enc["input_ids"].shape[1]:], skip_special_tokens=True)))
    del model
    n = len(rows)
    return {"hf_id": model_id, "device": device, "seconds": round(time.monotonic() - t0, 1), "n": n,
            "exact_match": sum(r["exact"] for r in rows), "exact_match_rate": sum(r["exact"] for r in rows) / n,
            "mean_char_edit_distance": sum(r["char_edit_distance"] for r in rows) / n,
            "mean_norm_edit_distance": round(sum(r["norm_edit_distance"] for r in rows) / n, 3), "rows": rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="auto")
    ap.add_argument("--models", default=",".join(MODELS))
    args = ap.parse_args(argv)
    sents = sentences()
    report = {"sentences": sents, "instruction": INSTRUCTION, "models": {}}
    for name in args.models.split(","):
        report["models"][name] = run(MODELS[name], args.device, sents)
        OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        r = report["models"][name]
        print(name, r["exact_match"], "/", r["n"], "mean edit", r["mean_char_edit_distance"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
