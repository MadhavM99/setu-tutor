"""Who writes what Raju says. The model WRITES; rules decide what is shown.

Two things Raju says, both written by the model when one is configured (see setu/llm.py):
  1. his line   - the planned claim ("ఖ = क") in his own words. The claim always comes from the bank.
  2. his reaction after the learner answers - thanks, celebration, or confusion. The verdict always comes
     from the checker; the model only words Raju's feelings about it.
Every model line passes the leak filter (setu/leakfilter.py). A rejected line's reasons are sent back so the
model can fix it (up to 3 drafts); after that, a fixed sentence is used. If the model is slow or down, fixed
sentences are used at once. The learner's own text is NEVER put into a prompt (no prompt injection).

  TemplateWriter  fixed Hindi sentences, no model (default, and the fallback)
  ModelWriter     a model from llm_from_env(): Gemma 4 on Google AI Studio, or your own vLLM server
"""
from __future__ import annotations
import random
from typing import List, Optional, Tuple
from .leakfilter import check_line, check_reaction
from .llm import clean_line, describe_error, llm_from_env

TEMPLATES_MISTAKE = ["मुझे लगता है {p} = {c} … सही है?", "{p} तो {c} ही है ना?", "मैंने याद किया: {p} = {c}। ठीक?"]
TEMPLATES_CORRECT = ["{p} = {c} … ये सही है ना?", "मैंने लिखा {p} = {c}। ठीक है?"]
SENTENCE_MISTAKE = ["मुझे कहना था “{p}”… तो मैंने लिखा: {c} — सही है?",
                    "“{p}” को Telugu में मैंने ऐसे लिखा: {c}। ठीक है ना?",
                    "Hindi में तो “{p}” बोलते हैं, तो Telugu में हुआ: {c}। है ना?"]
SENTENCE_CORRECT = ["“{p}” के लिए मैंने लिखा: {c}। ये ठीक है?", "मुझे लगता है “{p}” = {c}। सही?"]
REACTIONS = {
    "fixed":   ["अच्छा! तो {p} = {c}। धन्यवाद!", "ओह, मैं गलत था — {p} = {c}।", "अरे वाह, {p} = {c}! लिख लेता हूँ।"],
    "knows":   ["अब पक्का समझ गया! धन्यवाद, गुरु जी!", "अब नहीं भूलूँगा… शायद!", "शाबाश मुझे! और शाबाश आपको!"],
    "spot_ok": ["हाँ! मैं सही था, मज़ा आ गया।", "पता था मुझे! धन्यवाद।"],
    "doubt":   ["हम्म… पक्का? मुझे थोड़ा शक है।", "अरे, मैं और उलझ गया! एक बार कार्ड देखोगे?", "सच में? मुझे तो कुछ और लग रहा है…"],
}
GENERIC = {"fixed": "अच्छा, समझ गया!", "spot_ok": "हाँ! धन्यवाद।"}

PERSONA = ("You are Raju, a 12-year-old classmate of the user. You and the user just studied the SAME Telugu "
           "lesson cards (given below), but you mix things up. The user is teaching you. "
           "You talk like a real kid in casual, warm Hindi, and you think aloud using what the lesson said: the "
           "shape of the letter, the tip, the memory trick. Your mix-up comes from misremembering exactly that. "
           "RULES: ONE line, at most 130 characters, Hindi in Devanagari only. No English letters. The only Telugu "
           "you may write is the exact Telugu text you are given in the task. Never use the words क्योंकि, नियम, "
           "मतलब, व्याकरण. Reply with the line only, no quotes, no name.\n"
           "Examples of the style (with other letters): "
           "'दीदी ने कहा था नीचे वाली लकीर साँस है… पर मुझे तो वो लकीर दिखी ही नहीं! तो [అक्षर] = [गलत], है ना?' · "
           "'कार्ड पर घुमाव था ना? मुझे लगा घुमाव से कुछ नहीं बदलता… [అक्षर] = [गलत], सही?' · "
           "'वो कमल वाला शब्द याद है… उसी से मुझे लगा [అक्षर] = [गलत]। ठीक बोला?'")


class TemplateWriter:
    name = "template"

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()

    def draft(self, prompt: str, claim: str, mistake: bool, feedback: str = "", kind: str = "letter", **_) -> str:
        if kind == "sentence":
            t = self.rng.choice(SENTENCE_MISTAKE if mistake else SENTENCE_CORRECT)
            return t.format(p=prompt.rstrip("?।. "), c=claim)
        t = self.rng.choice(TEMPLATES_MISTAKE if mistake else TEMPLATES_CORRECT)
        return t.format(p=prompt, c=claim)

    def react(self, event: str, prompt: str = "", correct: str = "", wrong: str = "", feedback: str = "",
              context: str = "") -> str:
        if event in ("fixed", "spot_ok") and not prompt:
            return GENERIC[event]
        return self.rng.choice(REACTIONS[event]).format(p=prompt, c=correct)


class ModelWriter:
    """Raju written by a language model (any client with .chat(system, user) and .name)."""

    def __init__(self, llm, rng: Optional[random.Random] = None):
        self.llm, self.rng = llm, rng or random.Random()
        self.name = llm.name

    @classmethod
    def from_env(cls, rng: Optional[random.Random] = None) -> Optional["ModelWriter"]:
        llm = llm_from_env()
        return cls(llm, rng) if llm is not None else None

    def draft(self, prompt: str, claim: str, mistake: bool, feedback: str = "", context: str = "",
              avoid: str = "", kind: str = "letter", **_) -> str:
        """context: the lesson cards (from Tutor._raju_context). avoid: the right answer on a mistake turn."""
        if kind == "sentence":
            p = prompt.rstrip("?।. ")
            ask = (f"{context}\nTASK: you are trying to say “{p}” in Telugu, and you wrote: {claim}\n"
                   + ("You believe it is right, but it carries your Hindi habit. " if mistake else
                      "You think this is right and want the user to confirm. ")
                   + f"In ONE line (Hindi, at most 200 characters), think aloud like a classmate about why you wrote "
                   f"it this way and ask the user if it is right. The line MUST contain the Hindi sentence “{p}” "
                   f"and EXACTLY this Telugu: {claim}. Write no other Telugu.")
            if feedback:
                ask += f" Your previous line was rejected ({feedback}); write a new one that follows the rules."
            return clean_line(self.llm.chat(PERSONA, ask, max_tokens=140, temperature=0.8))
        if mistake:
            ask = (f"{context}\nTASK: you wrongly believe {prompt} = {claim}. In one line, think aloud about the "
                   f"lesson (a shape detail, the tip or the example you misremember) and ask the user if you are "
                   f"right. The line MUST contain exactly '{prompt} = {claim}'."
                   + (f" NEVER write '{avoid}'." if avoid else ""))
        else:
            ask = (f"{context}\nTASK: you believe {prompt} = {claim} and you are not fully sure. In one line, think "
                   f"aloud about the lesson card and ask the user to confirm. The line MUST contain exactly "
                   f"'{prompt} = {claim}'.")
        if feedback:
            ask += f" Your previous line was rejected ({feedback}); write a new one that follows the rules."
        return clean_line(self.llm.chat(PERSONA, ask, max_tokens=90, temperature=0.9))

    def react(self, event: str, prompt: str = "", correct: str = "", wrong: str = "", feedback: str = "",
              context: str = "") -> str:
        pair = f"'{prompt} = {correct}'" if prompt else ""
        ask = {
            "fixed": (f"The user just corrected you: it is {pair}. React with an 'aha!' that ties it to the lesson "
                      f"card (the shape or the trick), and thanks." if pair else
                      "The user just answered your question well. React with thanks.")
                     + (f" You may repeat {pair}. Do not mention '{wrong}'." if pair else ""),
            "knows": "You have now fully understood it, thanks to the user. Celebrate briefly and thank them like a teacher."
                     + (f" You may repeat {pair}." if pair else ""),
            "spot_ok": "The user confirmed that what you said was right. React happily and a bit proudly.",
            "doubt": "The user's answer to your question did not convince you. Sound confused and ask them to look "
                     "at the lesson card again. Do NOT give or hint at any answer. Write NO Telugu and no single letters.",
        }[event]
        if feedback:
            ask += f" Your previous line was rejected ({feedback}); write a new one that follows the rules."
        return clean_line(self.llm.chat(PERSONA, (context + "\nTASK: " if context else "") + ask,
                                        max_tokens=80, temperature=0.9))


def writer_from_env(rng: Optional[random.Random] = None):
    """The configured model if there is one, otherwise fixed sentences."""
    return ModelWriter.from_env(rng) or TemplateWriter(rng)


def _is_model(writer) -> bool:
    return not isinstance(writer, TemplateWriter)


def raju_line(writer, fallback: TemplateWriter, item, claim: str, mistake: bool, units, raju, seen, unit_id,
              max_drafts: int = 3, context: str = "", seen_words=None) -> Tuple[str, str, List[dict], int]:
    """Raju's line. Returns (line shown, source 'model'|'template', rejected drafts with reasons, model calls)."""
    rejected: List[dict] = []
    calls = 0
    if _is_model(writer):
        feedback = ""
        for _ in range(max_drafts):
            calls += 1
            try:
                d = writer.draft(item.prompt, claim, mistake, feedback, context=context,
                                 avoid=item.accepted[0] if mistake else "", kind=item.kind)
            except Exception as e:                      # server down, timeout, bad reply: never block the learner
                rejected.append({"draft": "", "reasons": [f"MODEL_ERROR: {describe_error(e)}"]})
                break
            dec = check_line(d, item, claim, mistake, units, raju, seen, unit_id, seen_words)
            if dec.ok:
                return d, "model", rejected, calls
            rejected.append({"draft": d, "reasons": dec.reasons})
            feedback = ", ".join(dec.reasons)
    return fallback.draft(item.prompt, claim, mistake, kind=item.kind), "template", rejected, calls


def raju_reaction(writer, fallback: TemplateWriter, event: str, item, units, seen,
                  max_drafts: int = 2, context: str = "") -> Tuple[str, str, List[dict], int]:
    """What Raju says after the checker's verdict. Same contract as raju_line."""
    p = item.prompt if item is not None else ""
    c = item.accepted[0] if item is not None else ""
    w = item.raju_wrong if item is not None else ""
    rejected: List[dict] = []
    calls = 0
    if _is_model(writer) and hasattr(writer, "react"):
        feedback = ""
        for _ in range(max_drafts):
            calls += 1
            try:
                d = writer.react(event, p, c, w, feedback, context=context)
            except Exception as e:
                rejected.append({"draft": "", "reasons": [f"MODEL_ERROR: {describe_error(e)}"]})
                break
            dec = check_reaction(d, item, event, units, seen)
            if dec.ok:
                return d, "model", rejected, calls
            rejected.append({"draft": d, "reasons": dec.reasons})
            feedback = ", ".join(dec.reasons)
    return fallback.react(event, p, c, w), "template", rejected, calls
