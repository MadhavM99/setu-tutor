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
- `agentic_tools`: the model is told the read-only tools (`tools.TOOLS`) and decides itself when to call one; each
  reply is either a tool call `{"tool": ..., "args": {...}}`, run by `tools.handle_reply`, or `{"final": "..."}`.
  At most MAX_STEPS model calls. The final sentence is re-checked by the leak filter whatever the tools said.
"""
import dataclasses
import json
import re

from setu.domain import leakfilter

from . import tools
from .llm import PROMPT_VERSION, Completion, parse_json

MAX_DRAFTS = 3
MAX_STEPS = 6
METHODS = ("tool", "resample", "prompt_only", "agentic_tools")
SYSTEM = ("तुम राजू हो, तेलुगु सीखने वाला एक हिंदी-भाषी विद्यार्थी। तुम्हें सिर्फ़ एक तेलुगु वाक्य लिखना है, जैसा एक कमज़ोर "
          "विद्यार्थी लिखता। कोई व्याख्या नहीं, कोई अनुवाद नहीं। जवाब सिर्फ़ JSON में दो: {\"sentence\": \"...\"}")
AGENT_SYSTEM = (
    "तुम राजू हो, तेलुगु सीखने वाला एक हिंदी-भाषी विद्यार्थी। तुम्हें एक तेलुगु वाक्य लिखना है, जैसा एक कमज़ोर विद्यार्थी "
    "लिखता। कोई व्याख्या नहीं, कोई अनुवाद नहीं।\n"
    "तुम्हारे पास ये जाँच-टूल हैं (सिर्फ़ जाँचते हैं, कुछ बदल नहीं सकते):\n"
    "- check_classmate_sentence(item_id, sentence): बताता है कि तुम्हारा वाक्य जाँच में पास होगा या नहीं, और क्यों नहीं।\n"
    "- check_hint_has_no_answer(item_id, hint): कोच के इशारे के लिए; तुम्हारे काम का नहीं।\n"
    "- check_level(text, scene_id): दृश्य की लाइनों के लिए; तुम्हारे काम का नहीं।\n"
    "हर जवाब में सिर्फ़ एक JSON object दो, और कुछ नहीं:\n"
    "टूल बुलाने के लिए: {\"tool\": \"<नाम>\", \"args\": {...}}\n"
    "आख़िरी वाक्य देने के लिए: {\"final\": \"<तेलुगु वाक्य>\"}\n"
    "आख़िरी वाक्य से पहले उसे check_classmate_sentence से जाँच लो।")
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


@dataclasses.dataclass(frozen=True)
class Draft:
    sentence: str | None
    reasons: tuple
    completion: Completion


@dataclasses.dataclass(frozen=True)
class Step:
    """One model call of the agentic method, as logged: what the model asked for and what it got back."""
    kind: str  # tool_call | final | provider_error
    tool: str | None
    args: dict | None
    result: dict | str | None  # the tool's result or exact error string; for a final, the filter reasons
    completion: Completion


@dataclasses.dataclass(frozen=True)
class RajuTurn:
    text: str  # what the learner sees
    source: str  # model | bank
    drafts: tuple  # every draft with its filter reasons (agentic: one per model call; tool steps carry TOOL_STEP)
    method: str
    steps: tuple = ()  # agentic_tools only: every step, in order


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
    if method == "agentic_tools":
        return _agentic(provider, ctx, rule_title, hindi_meaning, bank_sentence)
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


def _agentic(provider, ctx: leakfilter.Context, rule_title: str, hindi_meaning: str, bank_sentence: str) -> RajuTurn:
    item_id = ctx.item.item_id

    def context_for(iid):
        if iid != item_id:
            raise KeyError(iid)
        return ctx

    task = _prompt(ctx, rule_title, hindi_meaning)[1]["content"]
    msgs = [{"role": "system", "content": AGENT_SYSTEM}, {"role": "user", "content": f"item_id: {item_id}\n{task}"}]
    steps: list[Step] = []
    drafts: list[Draft] = []
    for _ in range(MAX_STEPS):
        c = provider.complete(list(msgs), max_tokens=200)
        if not c.ok:
            steps.append(Step("provider_error", None, None, c.error, c))
            drafts.append(Draft(None, ("NO_SENTENCE",), c))
            continue
        reply = _FENCE.sub("", c.text.strip())
        msgs.append({"role": "assistant", "content": reply})
        try:
            obj = json.loads(reply)
        except ValueError:
            obj = None
        if isinstance(obj, dict) and set(obj) == {"final"}:
            sentence = obj["final"] if isinstance(obj["final"], str) else None
            reasons = tuple(leakfilter.check_sentence(sentence, ctx)) if sentence else ("NO_SENTENCE",)
            steps.append(Step("final", None, None, list(reasons), c))
            drafts.append(Draft(sentence, reasons, c))
            if not reasons:
                return RajuTurn(sentence, "model", tuple(drafts), "agentic_tools", tuple(steps))
            msgs.append({"role": "user", "content": "जाँच ने यह वाक्य लौटा दिया: " + ", ".join(reasons) +
                         "। फिर से कोशिश करो।"})
            continue
        result = tools.handle_reply(reply, context_for=context_for, planned_item=item_id)
        name = obj.get("tool") if isinstance(obj, dict) else None
        args = obj.get("args") if isinstance(obj, dict) and isinstance(obj.get("args"), dict) else None
        steps.append(Step("tool_call", name if isinstance(name, str) else None, args, result, c))
        drafts.append(Draft(None, ("TOOL_STEP",), c))
        msgs.append({"role": "user", "content": "TOOL RESULT: " + (result if isinstance(result, str)
                                                                   else json.dumps(result, ensure_ascii=False))})
    return RajuTurn(bank_sentence, "bank", tuple(drafts), "agentic_tools", tuple(steps))


VERSION = PROMPT_VERSION
