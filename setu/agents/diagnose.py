"""Diagnostic reasoning over a learner's correction (TASKS.md task 8; scored in task 15). Research only.

Given the Hindi meaning, the classmate's sentence and the learner's correction, the model reasons in separate,
scored steps: which word is wrong -> which rule it breaks -> which error type -> a self-check that may revise the
three answers. Each step is its own model call and is stored with its parsed answer, whether that answer is valid
(a word that is in the correction, a rule id from the offered list, a type from ERROR_TYPES) and the completion.
Nothing here grades the learner or changes state: the checker stays the only source of verdicts, and these
diagnoses are compared with it.

Methods (task 15):
- `stepwise`: the four steps;
- `no_self_check`: the first three steps (ablation);
- `direct`: one call that answers all three at once, no intermediate steps (baseline).
"""
import dataclasses

from .llm import Completion, parse_json

METHODS = ("stepwise", "no_self_check", "direct")
STEPS = ("wrong_word", "rule", "error_type", "self_check")
ERROR_TYPES = {
    "habit_kept": "the Hindi habit (the classmate's mistake) is still in the correction",
    "spelling_slip": "the right sentence with a one-letter spelling slip",
    "word_missing_or_extra": "the mistake is fixed but a word is missing or extra",
    "other_sentence": "a correct sentence, but for a different meaning",
    "correct": "nothing is wrong",
    "other": "wrong in some other way",
}
# the checker's reason codes in the same terms, for agreement with the checker
CHECKER_TO_TYPE = {"planted_error_unchanged": "habit_kept", "planted_error_present": "habit_kept",
                   "spelling_near_miss": "spelling_slip", "extra_or_missing_word": "word_missing_or_extra",
                   "other_item_sentence": "other_sentence", "accepted_form": "correct",
                   "accepted_pattern": "correct", "unknown_form": "other"}
SYSTEM = ("You are a careful Telugu teacher. A Hindi-speaking learner of Telugu tried to correct a classmate's Telugu "
          "sentence. You diagnose the learner's correction step by step. Reply with one JSON object only.")


@dataclasses.dataclass(frozen=True)
class DiagnosisStep:
    name: str  # one of STEPS, or "direct"
    answer: dict | None  # the parsed JSON reply
    valid: bool
    completion: Completion


@dataclasses.dataclass(frozen=True)
class Diagnosis:
    method: str
    steps: tuple
    wrong_word: str | None  # a word of the correction, "none", or None when no valid answer
    rule_id: str | None
    error_type: str | None
    revised: bool  # the self-check changed at least one answer


def _context(hindi_meaning, classmate_sentence, learner_text, rules):
    offered = "\n".join(f"- {rid}: {title}" for rid, title in rules)
    return (f"Meaning (Hindi): {hindi_meaning}\nClassmate's sentence: {classmate_sentence}\n"
            f"Learner's correction: {learner_text}\nRules:\n{offered}")


def _types():
    return "\n".join(f"- {k}: {v}" for k, v in ERROR_TYPES.items())


def diagnose(provider, *, hindi_meaning: str, classmate_sentence: str, learner_text: str,
             rules: list[tuple[str, str]], method: str = "stepwise") -> Diagnosis:
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    words = set(learner_text.split())
    rule_ids = {rid for rid, _ in rules}
    checks = {"wrong_word": lambda v: v == "none" or v in words, "rule_id": lambda v: v in rule_ids,
              "error_type": lambda v: v in ERROR_TYPES}
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": _context(hindi_meaning, classmate_sentence, learner_text, rules)}]
    steps: list[DiagnosisStep] = []

    def ask(name, question, keys):
        msgs.append({"role": "user", "content": question})
        c = provider.complete(list(msgs), max_tokens=150, temperature=0.0)
        obj = parse_json(c.text, keys) if c.ok else None
        valid = obj is not None and all(checks[k](obj[k]) for k in keys if k in checks)
        msgs.append({"role": "assistant", "content": c.text or ""})
        steps.append(DiagnosisStep(name, obj, valid, c))
        return obj if valid else None

    if method == "direct":
        obj = ask("direct", "Answer all three at once. error_type is one of:\n" + _types() +
                  '\nReply {"wrong_word": "<one word of the correction, or none>", "rule_id": "<a rule id above>", '
                  '"error_type": "<type>"}', ("wrong_word", "rule_id", "error_type")) or {}
        return Diagnosis(method, tuple(steps), obj.get("wrong_word"), obj.get("rule_id"), obj.get("error_type"), False)

    word = ask("wrong_word", 'Step 1. Which single word of the learner\'s correction is wrong? Copy it exactly. '
               'Reply {"wrong_word": "<word>"} or {"wrong_word": "none"}.', ("wrong_word",))
    rule = ask("rule", 'Step 2. Which rule does that mistake break? Reply {"rule_id": "<a rule id above>"}.',
               ("rule_id",))
    etype = ask("error_type", "Step 3. Which error type is it? One of:\n" + _types() +
                '\nReply {"error_type": "<type>"}.', ("error_type",))
    answers = {"wrong_word": word and word["wrong_word"], "rule_id": rule and rule["rule_id"],
               "error_type": etype and etype["error_type"]}
    if method == "stepwise":
        check = ask("self_check", "Step 4. Check your three answers against the sentences again. Keep each answer "
                    "that is right and fix any that is wrong. Reply {\"wrong_word\": ..., \"rule_id\": ..., "
                    "\"error_type\": ...}.", ("wrong_word", "rule_id", "error_type"))
        if check:
            revised = {k: check[k] for k in answers}
            changed = revised != answers
            return Diagnosis(method, tuple(steps), revised["wrong_word"], revised["rule_id"], revised["error_type"],
                             changed)
    return Diagnosis(method, tuple(steps), answers["wrong_word"], answers["rule_id"], answers["error_type"], False)
