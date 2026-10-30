"""Ravi, the native friend (paper §4): opens each rule lesson inside its scene. He sets the scene in Hindi and says
the lesson's Telugu sentence the way a friend from Hyderabad would, so the rule is first met in use.

Guard (rules only): Hindi narration, no English letters, short; every Telugu word must be one the learner has met
or a word of this lesson's sentences (Token Miss Rate = 0, paper Eq. 1); the lesson's first Telugu sentence must
be in it exactly. Made once per lesson and kept for everyone; without a model, a fixed scene line is used.
"""
from __future__ import annotations
import re
from typing import Tuple
from .contracts import Unit
from .llm import describe_error
from .text import normalize, telugu_to_deva

SYSTEM = ("You are Ravi, a friendly young man from Hyderabad who speaks Telugu and Hindi. You help a Hindi-speaking "
          "friend who is new to the city. Write 2 short lines: first set the scene in simple Hindi (Devanagari), then "
          "say ONE line in Telugu, which must be exactly the Telugu sentence you are given. No other Telugu words. "
          "No English letters. At most 260 characters. Reply with the lines only.")


def check_friend(text: str, unit: Unit, seen_words: set) -> list:
    n = normalize(text)
    reasons = []
    if not n or len(n) > 300 or any(c.isascii() and c.isalpha() for c in n):
        reasons.append("FORMAT")
    allowed = set(seen_words) | {normalize(w) for l in unit.lesson for w in l.telugu.split()}
    words = [normalize(w) for w in re.findall(r"[ఀ-౿]+", n)]
    if any(w not in allowed for w in words):
        reasons.append("UNSEEN_TELUGU")
    if normalize(unit.lesson[0].telugu) not in n:
        reasons.append("MISSING_SENTENCE")
    return reasons


def fixed_line(unit: Unit, scene: str) -> str:
    l = unit.lesson[0]
    return f"{scene}\nरवि: “{l.telugu}” ({telugu_to_deva(l.telugu)}) — यानी “{l.hindi}”"


class Friend:
    def __init__(self, llm):
        self.llm = llm

    def scene_line(self, unit: Unit, scene: str, seen_words: set) -> Tuple[str, str]:
        l = unit.lesson[0]
        ask = (f"SCENE: {scene}\nThe Telugu sentence to say: {l.telugu} (it means: {l.hindi})\n"
               f"Write the 2 lines.")
        fb = ""
        for _ in range(2):
            try:
                text = (self.llm.chat(SYSTEM, ask + fb, max_tokens=160, temperature=0.7) or "").strip()
            except Exception as e:
                return fixed_line(unit, scene), f"fixed ({describe_error(e)})"
            bad = check_friend(text, unit, seen_words)
            if not bad:
                return text, "model"
            fb = f"\n(Rejected: {', '.join(bad)}. Fix that.)"
        return fixed_line(unit, scene), "fixed"
