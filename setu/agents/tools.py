"""Model-facing read-only tools and the JSON tool envelope (api-and-tool-contracts.md Part A, P-TOOL-01..08).

A model replies with one JSON object `{"tool": <name>, "args": {...}}`; the harness validates and runs it. Every
tool is a pure check: none can write. Invalid calls get the exact documented error strings so the model can correct
the call. The harness re-runs `check_classmate_sentence` on submission and never trusts an earlier result.
"""
import dataclasses
import json
import re
from collections.abc import Callable

from setu.content.schema import ITEM_ID, RULE_ID
from setu.domain import leakfilter

MAX_REPLY = 2000
MAX_SENTENCE = leakfilter.MAX_SENTENCE
_MULTI = re.compile(r"[.!?।॥]\s*\S|\n")
_SCRIPT_NAME = {"telugu": "Telugu", "devanagari": "Devanagari"}
_SCRIPT_RE = {"telugu": re.compile(r"[ఀ-౿]"), "devanagari": re.compile(r"[ऀ-ॿ]")}


@dataclasses.dataclass(frozen=True)
class Tool:
    name: str
    args: tuple
    read_only: bool = True


TOOLS = {
    "check_classmate_sentence": Tool("check_classmate_sentence", ("item_id", "sentence")),
    "check_hint_has_no_answer": Tool("check_hint_has_no_answer", ("item_id", "hint")),
    "check_level": Tool("check_level", ("text", "scene_id")),
}

MALFORMED = 'ERROR malformed_json: reply with one JSON object {"tool": ..., "args": {...}} and nothing else.'


def _bad(arg: str, msg: str) -> str:
    return f"ERROR invalid_argument {arg}: {msg}"


def _check_item_id(v, planned: str | None) -> str | None:
    if not isinstance(v, str):
        return _bad("item_id", "must be a string like \"HI-TE-002-a\".")
    if RULE_ID.match(v):
        return _bad("item_id", f'"{v}" is a rule id; pass an item id like "{v}-a".')
    if not ITEM_ID.match(v):
        return _bad("item_id", f'"{v}" does not match HI-TE-NNN-x (example: HI-TE-002-a).')
    if planned is not None and v != planned:
        return _bad("item_id", f'"{v}" is not the planned item for this turn.')
    return None


def _check_sentence_arg(s, script: str) -> str | None:
    name = _SCRIPT_NAME[script]
    if not isinstance(s, str) or not s.strip():
        return _bad("sentence", f"empty; pass one {name} sentence.")
    if re.search(r"[A-Za-z]", s):
        return _bad("sentence", f"contains Latin letters; pass {name} script only, no romanization or English.")
    if not _SCRIPT_RE[script].search(s):
        return _bad("sentence", f"no {name} characters found; pass the sentence in {name} script.")
    if _MULTI.search(s.strip()):
        return _bad("sentence", "more than one sentence or line; pass exactly one sentence.")
    if len(s) > MAX_SENTENCE:
        return _bad("sentence", f"longer than {MAX_SENTENCE} characters; pass one short sentence.")
    if re.search(r"[()\[\]{}]", s):
        return _bad("sentence", "contains a gloss or translation in brackets; pass the sentence only.")
    return None


def handle_reply(reply: str, *, context_for: Callable[[str], leakfilter.Context], planned_item: str | None,
                 level_context_for: Callable[[str], dict] | None = None):
    """Run one tool call from a model reply. Returns the tool result (dict) or an exact error string."""
    if len(reply or "") > MAX_REPLY:
        return f'ERROR oversized_input: argument "reply" is longer than {MAX_REPLY} characters.'
    try:
        call = json.loads(reply)
    except (TypeError, ValueError):
        return MALFORMED
    if not isinstance(call, dict) or set(call) != {"tool", "args"} or not isinstance(call["args"], dict):
        return MALFORMED
    name, args = call["tool"], call["args"]
    if name not in TOOLS:
        return f'ERROR unknown_tool: "{name}" is not a tool; available: {", ".join(TOOLS)}.'
    extra = set(args) - set(TOOLS[name].args)
    if extra:
        return _bad("args", f'unexpected "{min(extra)}"; pass {" and ".join(TOOLS[name].args)} only.')

    if name in ("check_classmate_sentence", "check_hint_has_no_answer"):
        err = _check_item_id(args.get("item_id"), planned_item)
        if err:
            return err
        try:
            ctx = context_for(args["item_id"])
        except KeyError:
            return _bad("item_id", f'"{args["item_id"]}" is not in the rule bank.')
        if name == "check_hint_has_no_answer":
            hint = args.get("hint")
            if not isinstance(hint, str) or len(hint) > leakfilter.MAX_HINT:
                return _bad("hint", f"pass one hint of at most {leakfilter.MAX_HINT} characters.")
            reasons = leakfilter.check_hint(ctx.item, hint)
            return {"ok": not reasons, "reasons": reasons}
        err = _check_sentence_arg(args.get("sentence"), ctx.item.target_script)
        if err:
            return err
        reasons = leakfilter.check_sentence(args["sentence"], ctx)
        return {"ok": not reasons, "reasons": reasons}

    # check_level
    text = args.get("text")
    if not isinstance(text, str) or len(text) > leakfilter.MAX_LINE:
        return _bad("text", f"longer than {leakfilter.MAX_LINE} characters; pass one short line.")
    if level_context_for is None:
        return _bad("scene_id", f'"{args.get("scene_id")}" is not an approved scene.')
    try:
        lc = level_context_for(args.get("scene_id"))
    except KeyError:
        return _bad("scene_id", f'"{args.get("scene_id")}" is not an approved scene.')
    r = leakfilter.check_level(text, **lc)
    return {"ok": r.ok, "reasons": list(r.reasons), "oov_share": r.oov_share, "hindi_share": r.hindi_share,
            "band": r.band}
