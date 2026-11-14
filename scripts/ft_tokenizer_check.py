"""Base-model check before QLoRA (TASKS.md task 10, step 1): Telugu tokenizer fertility and whether each ~1B instruct
model can write readable Telugu at all. Development only; writes reports/ft_model_check.json.

Needs transformers + torch, which are NOT project dependencies. Use a separate venv:

    uv venv /tmp/ftvenv && VIRTUAL_ENV=/tmp/ftvenv uv pip install transformers==4.57.1 torch==2.8.0 accelerate pyyaml
    PYTHONPATH=. /tmp/ftvenv/bin/python scripts/ft_tokenizer_check.py               # fertility + generation
    PYTHONPATH=. /tmp/ftvenv/bin/python scripts/ft_tokenizer_check.py --no-generate # tokenizers only

Fertility = tokens per whitespace word over every distinct Telugu run in content/hi-te and content/te-hi (Hindi runs
are measured too, for reference). Lower is better: fewer tokens per word means more context and an easier target.

Readability: each model is asked (greedy, its own chat template) to translate 8 fixed Hindi sentences into Telugu.
These are written for this check and are not from the frozen evaluation cases. Per output: share of letters in
Telugu script, and share of Telugu words that are known words (lexicon + rule-bank forms), a proxy for real Telugu
rather than script-shaped noise. Both are reported; nobody has read the outputs for meaning (no native check).

Llama 3.2 and Gemma 3 are gated on Hugging Face; the `unsloth/` repos are ungated copies of the same weights and
tokenizers, used here so no token is needed.
"""
import argparse
import json
import re
import statistics
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/ft_model_check.json"
CANDIDATES = {
    "Qwen2.5-1.5B-Instruct": "Qwen/Qwen2.5-1.5B-Instruct",
    "Llama-3.2-1B-Instruct": "unsloth/Llama-3.2-1B-Instruct",
    "Gemma-3-1B-it": "unsloth/gemma-3-1b-it",
}
TELUGU_RUN = re.compile(r"[ఀ-౿]+(?:\s+[ఀ-౿]+)*")
DEVA_RUN = re.compile(r"[ऀ-ॿ]+(?:\s+[ऀ-ॿ]+)*")
TELUGU_LETTER = re.compile(r"[ఀ-౿]")
LETTER = re.compile(r"[^\W\d_]", re.UNICODE)
PROMPTS_HI = ["मुझे चाय पसंद है।", "यह मेरी किताब है।", "तुम कहाँ रहते हो?", "मुझे पानी चाहिए।",
              "वह स्कूल में पढ़ती है।", "हम कल बाज़ार जाएँगे।", "मेरा नाम राजू है।", "आज मौसम अच्छा है।"]
INSTRUCTION = "Translate this Hindi sentence into Telugu. Write only the Telugu sentence in Telugu script.\n\n"


def corpus():
    tel, hin = set(), set()
    for folder in ("hi-te", "te-hi"):
        for p in sorted((ROOT / "content" / folder).rglob("*.yaml")):
            text = p.read_text(encoding="utf-8")
            tel.update(m.group(0) for m in TELUGU_RUN.finditer(text))
            hin.update(m.group(0) for m in DEVA_RUN.finditer(text))
    return sorted(tel), sorted(hin)


def known_telugu_words() -> set:
    words = set()
    lex = yaml.safe_load((ROOT / "content/hi-te/lexicon.yaml").read_text(encoding="utf-8")) or []
    words.update(e["telugu"] for e in lex if e.get("telugu"))
    for p in sorted((ROOT / "content/hi-te/rules").glob("*.yaml")):
        rule = yaml.safe_load(p.read_text(encoding="utf-8"))
        for it in rule["items"]:
            for f in [it["correct_form"], it.get("wrong_form") or "", *(v["form"] for v in it["accepted_variants"])]:
                words.update(f.split())
    return {w for w in words if TELUGU_LETTER.search(w)}


def fertility(tok, runs) -> dict:
    words = sum(len(r.split()) for r in runs)
    toks = sum(len(tok.encode(r, add_special_tokens=False)) for r in runs)
    unk = tok.unk_token_id
    n_unk = sum(tok.encode(r, add_special_tokens=False).count(unk) for r in runs) if unk is not None else 0
    return {"runs": len(runs), "words": words, "tokens": toks, "tokens_per_word": round(toks / words, 3),
            "unk_tokens": n_unk}


def readability(model_id, tok, known, max_new_tokens=48, device="auto") -> dict:
    import torch
    from transformers import AutoModelForCausalLM

    if device == "auto":  # MPS on macOS 14 aborts on >4 GB arrays (large-vocab logits), so auto means cuda or cpu
        device = "cuda" if torch.cuda.is_available() else "cpu"
    t0 = time.monotonic()
    model = AutoModelForCausalLM.from_pretrained(model_id, dtype=torch.float16 if device != "cpu" else
                                                 torch.float32).to(device)
    model.eval()
    rows = []
    for hi in PROMPTS_HI:
        msgs = [{"role": "user", "content": INSTRUCTION + hi}]
        enc = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True)
        enc = {k: v.to(device) for k, v in enc.items()}
        ids = enc["input_ids"]
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False,
                                 pad_token_id=tok.pad_token_id or tok.eos_token_id)
        text = tok.decode(out[0, ids.shape[1]:], skip_special_tokens=True).strip()
        letters = LETTER.findall(text)
        tel_words = [w for w in re.findall(r"[ఀ-౿]+", text)]
        rows.append({"hindi": hi, "output": text,
                     "telugu_letter_share": round(sum(bool(TELUGU_LETTER.match(c)) for c in letters) / len(letters), 3)
                     if letters else 0.0,
                     "telugu_words": len(tel_words),
                     "known_word_share": round(sum(w in known for w in tel_words) / len(tel_words), 3)
                     if tel_words else 0.0})
    del model
    return {"device": device, "seconds": round(time.monotonic() - t0, 1), "outputs": rows,
            "mean_telugu_letter_share": round(statistics.mean(r["telugu_letter_share"] for r in rows), 3),
            "mean_known_word_share": round(statistics.mean(r["known_word_share"] for r in rows), 3),
            "outputs_with_telugu": sum(r["telugu_words"] > 0 for r in rows)}


def recommend(models: dict) -> dict:
    """Rule, fixed before looking at the numbers: among models whose outputs are mostly Telugu script (mean share
    >= 0.8 and at least 6 of 8 outputs contain Telugu), pick the lowest Telugu fertility; ties by known-word share."""
    ok = {k: v for k, v in models.items() if v.get("readability")
          and v["readability"]["mean_telugu_letter_share"] >= 0.8 and v["readability"]["outputs_with_telugu"] >= 6}
    if not ok:
        return {"model": None, "rule": recommend.__doc__.split("Rule, ")[1].strip(),
                "reason": "no candidate passed the readability bar (or generation was not run)"}
    best = min(ok, key=lambda k: (ok[k]["telugu"]["tokens_per_word"], -ok[k]["readability"]["mean_known_word_share"]))
    return {"model": best, "hf_id": CANDIDATES[best], "passed_readability": sorted(ok),
            "rule": "lowest Telugu tokens/word among models with mean Telugu-script share >= 0.8 and >= 6/8 Telugu "
                    "outputs; ties by known-word share"}


def main(argv=None) -> int:
    from transformers import AutoTokenizer

    ap = argparse.ArgumentParser()
    ap.add_argument("--no-generate", action="store_true")
    ap.add_argument("--models", default=",".join(CANDIDATES))
    ap.add_argument("--device", default="auto", help="auto (cuda or cpu), cpu, cuda, mps")
    args = ap.parse_args(argv)
    tel, hin = corpus()
    known = known_telugu_words()
    report = {"corpus": {"telugu_runs": len(tel), "hindi_runs": len(hin), "known_telugu_words": len(known)},
              "models": {}}
    for name in args.models.split(","):
        hf = CANDIDATES[name]
        tok = AutoTokenizer.from_pretrained(hf)
        m = {"hf_id": hf, "vocab_size": tok.vocab_size, "telugu": fertility(tok, tel), "hindi": fertility(tok, hin)}
        if not args.no_generate:
            m["readability"] = readability(hf, tok, known, device=args.device)
        report["models"][name] = m
        OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")  # per model
        print(name, json.dumps({k: v for k, v in m.items() if k != "readability"}, ensure_ascii=False))
    report["recommendation"] = recommend(report["models"])
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["recommendation"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
