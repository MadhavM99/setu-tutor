"""Didi: the AI teacher. She teaches inside the lesson, and only from the lesson.

  ask(unit, question)  the learner asks a doubt while on the cards or the drill; Didi answers from the facts of
                       this lesson (and the letters already learned). Not available during the scored check or
                       while the learner teaches Raju, so she can never hand over an answer that is being tested.
  hint(unit, item)     after a miss in the drill: a nudge towards the shape or the trick, never the answer.

Guards (leakfilter.check_didi, rules only): Hindi only; only Telugu letters the learner has already been shown;
never pairs a letter with a sound other than the one in the lessons; a hint never contains the answer.
A rejected draft goes back with the reasons (2 tries); then Didi says she will check with the teacher, and the
question goes to the Teacher queue. The learner's question is the only thing they type that reaches a model, and
whatever comes back still has to pass the rules.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from .contracts import Item, Unit
from .leakfilter import check_didi
from .llm import describe_error

SYSTEM = ("You are Didi, a warm, patient Telugu teacher for Hindi speakers. You explain in simple, friendly Hindi "
          "(Devanagari script only, no English letters). Use ONLY the lesson facts given to you; never guess other "
          "Telugu letters or words. If the question goes beyond the facts, say kindly that it comes in a later "
          "lesson. When you write a Telugu letter with its sound, write it exactly as 'X = Y' from the facts. "
          "At most 3 short sentences.")
UNSURE = "ये मैं अभी पक्का नहीं बता सकती — मैंने teacher से पूछ लिया है। तब तक कार्ड का आकार और तरकीब देखो।"


class Didi:
    def __init__(self, llm, units: List[Unit]):
        self.llm, self.units = llm, units
        self.pairs: Dict[str, str] = {l.telugu: l.hindi for u in units for l in u.lesson}

    @property
    def name(self) -> str:
        return getattr(self.llm, "name", "")

    def facts(self, unit: Unit, learned: List[str]) -> str:
        cards = "\n".join(f"- {l.telugu} = {l.hindi}. दिखता है: {l.shape or '-'}. तरकीब: {l.mnemonic or '-'}. "
                          f"उदाहरण: {l.example or '-'}" for l in unit.lesson)
        before = [f"{l.telugu} = {l.hindi}" for u in self.units if u.unit_id in learned and u.unit_id != unit.unit_id
                  for l in u.lesson]
        return (f"LESSON: {unit.title}\nTIP: {unit.tip or '-'}\nCARDS:\n{cards}"
                + (f"\nALREADY LEARNED: {', '.join(before)}" if before else ""))

    def _run(self, ask: str, seen: set, avoid=(), tries: int = 2) -> Tuple[str, str, List[dict]]:
        rejected, fb = [], ""
        for _ in range(tries):
            try:
                text = (self.llm.chat(SYSTEM, ask + fb, max_tokens=220, temperature=0.6) or "").strip()
            except Exception as e:
                rejected.append({"draft": "", "reasons": [f"MODEL_ERROR: {describe_error(e)}"]})
                break
            text = " ".join(text.split())
            dec = check_didi(text, seen, self.pairs, avoid)
            if dec.ok:
                return text, "model", rejected
            rejected.append({"draft": text, "reasons": dec.reasons})
            fb = f"\n(Your last answer was rejected: {', '.join(dec.reasons)}. Fix that.)"
        return "", "none", rejected

    def ask(self, unit: Unit, question: str, seen: set, learned: List[str]) -> Tuple[str, str, List[dict]]:
        q = " ".join((question or "").split())[:300]
        text, src, rej = self._run(f"{self.facts(unit, learned)}\n\nSTUDENT'S QUESTION: {q}\nAnswer as Didi.", seen)
        return (text, src, rej) if text else (UNSURE, "fallback", rej)

    def hint(self, unit: Unit, item: Item, seen: set, learned: List[str]) -> Tuple[str, str, List[dict]]:
        ask = (f"{self.facts(unit, learned)}\n\nThe student just got '{item.prompt}' wrong. Give ONE short hint "
               f"(1–2 sentences) about its shape or its memory trick so they can find the answer themselves. "
               f"Do NOT write the answer '{item.accepted[0]}' and do not write '{item.prompt} = …'.")
        avoid = list(item.accepted)
        if item.kind == "sentence":                       # no word of the right sentence that is not in the mistake
            mistake = set(item.raju_wrong.split())
            avoid += [w for a in item.accepted for w in a.split() if w not in mistake]
            ask = (f"{self.facts(unit, learned)}\n\nThe student is writing “{item.prompt}” in Telugu and got it wrong. "
                   f"Give ONE short hint in Hindi (1–2 sentences) about the RULE (what is different from Hindi here), "
                   f"so they can fix it themselves. Do NOT write the Telugu answer or any of its words.")
        return self._run(ask, seen, avoid=avoid)
