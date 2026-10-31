"""Raju, the classmate (P-ARCH-03, P-CLS-02..08, P-TOOL-01; classmate-output-contract.md). Slice: mid-submission.

The model only proposes the text of Raju's sentence. Every proposal goes through the deterministic leak filter
(`leakfilter.check_sentence`): one planted error of the planned rule only (planted turn) or an accepted form (no-error
turn), no unseen words (TMR), no answer leak, no unknown-rule forms, student register only. Nothing the model says
can grade, update mastery, change Raju's memory, the ledger or a schedule: it returns a string, and the caller shows
the approved bank sentence whenever no proposal passes.

Methods (P-MODEL ablation; compared in `setu.research.generation_baselines`):
- `tool`:      up to MAX_DRAFTS drafts; after each rejected draft the filter's reasons are given back to the model;
- `resample`:  up to MAX_DRAFTS independent drafts, no feedback;
- `prompt_only`: one draft. Used only to measure the baseline; the app never shows an unfiltered draft.
"""
import dataclasses

from setu.domain import leakfilter

from .llm import PROMPT_VERSION, Completion, parse_json

MAX_DRAFTS = 3
METHODS = ("tool", "resample", "prompt_only")
SYSTEM = ("तुम राजू हो, तेलुगु सीखने वाला एक हिंदी-भाषी विद्यार्थी। तुम्हें सिर्फ़ एक तेलुगु वाक्य लिखना है, जैसा एक कमज़ोर "
          "विद्यार्थी लिखता। कोई व्याख्या नहीं, कोई अनुवाद नहीं। जवाब सिर्फ़ JSON में दो: {\"sentence\": \"...\"}")


@dataclasses.dataclass(frozen=True)
class Draft:
    sentence: str | None
    reasons: tuple
    completion: Completion


@dataclasses.dataclass(frozen=True)
class RajuTurn:
    text: str  # what the learner sees
    source: str  # model | bank
    drafts: tuple  # every draft with its filter reasons
    method: str


def _prompt(ctx: leakfilter.Context, rule_title: str, hindi_meaning: str, feedback=None):
    if ctx.turn == "planted":
        task = (f"मतलब: “{hindi_meaning}”। यह वाक्य तेलुगु में लिखो, पर इस नियम में हिंदी वाली एक गलती करो: {rule_title}। "
                f"राजू ने पिछली बार ऐसा लिखा था: {ctx.item.wrong_form}")
    else:
        task = f"मतलब: “{hindi_meaning}”। यह वाक्य तेलुगु में बिल्कुल सही लिखो।"
    words = " ".join(sorted(ctx.seen_words))
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"{task}\nसिर्फ़ इन शब्दों का इस्तेमाल करो: {words}"}]
    if feedback:
        msgs.append({"role": "user", "content": "जाँच ने यह वाक्य लौटा दिया: " + ", ".join(feedback) +
                     "। फिर से सिर्फ़ JSON में लिखो।"})
    return msgs


def propose(provider, ctx: leakfilter.Context, *, rule_title: str, hindi_meaning: str, bank_sentence: str,
            method: str = "tool") -> RajuTurn:
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    drafts: list[Draft] = []
    n = 1 if method == "prompt_only" else MAX_DRAFTS
    feedback = None
    for _ in range(n):
        c = provider.complete(_prompt(ctx, rule_title, hindi_meaning, feedback if method == "tool" else None),
                              max_tokens=120)
        obj = parse_json(c.text, ("sentence",)) if c.ok else None
        sentence = obj["sentence"] if obj and isinstance(obj["sentence"], str) else None
        reasons = tuple(leakfilter.check_sentence(sentence, ctx)) if sentence else ("NO_SENTENCE",)
        drafts.append(Draft(sentence, reasons, c))
        if not reasons:
            return RajuTurn(sentence, "model", tuple(drafts), method)
        feedback = reasons
    return RajuTurn(bank_sentence, "bank", tuple(drafts), method)


VERSION = PROMPT_VERSION
