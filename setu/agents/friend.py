"""The native friend रवि (P-ARCH-08, F-SCENE, X-ARCH-01; session-and-exchange.md §6). Slice S8.

The friend says only teacher-approved scene lines. A model may at most *pick* one of the approved forms of the
current turn (the line or an approved variant of it): any other proposal, however plausible, is rejected and the
approved line is shown. There is no path from model text to the learner that does not match the bank exactly.
Every line shown is measured with `check_level`: words outside the learner's seen words and the scene vocabulary
(out-of-band words) and the share of Hindi tokens are returned for the scene telemetry.
"""
import dataclasses

from setu.domain import leakfilter
from setu.domain.normalise import canonical
from setu.domain.tokenize import tokens

VERSION = "friend-1"


@dataclasses.dataclass(frozen=True)
class ApprovedLine:
    text: str
    variants: tuple = ()  # approved alternative wordings of the same line


@dataclasses.dataclass(frozen=True)
class FriendLine:
    text: str
    source: str  # bank | model (a model that chose an approved form)
    rejected: tuple  # why a model proposal was not used
    out_of_band: tuple
    hindi_share: float
    version: str = VERSION


def choose_line(line: ApprovedLine, proposal: str | None, *, seen_words, scene_words, learner_band: str) -> FriendLine:
    approved = {canonical(f): f for f in (line.text, *line.variants)}
    text, source, rejected = line.text, "bank", ()
    if proposal is not None:
        match = approved.get(canonical(proposal)) if isinstance(proposal, str) else None
        if match is not None:
            text, source = match, "model"
        else:
            rejected = ("NOT_APPROVED",)
    known = set(map(canonical, seen_words)) | set(map(canonical, scene_words))
    out_of_band = tuple(w for w in tokens(text) if w not in known and not w.isdigit())
    level = leakfilter.check_level(text, seen_words=seen_words, scene_words=scene_words, learner_band=learner_band)
    return FriendLine(text, source, rejected, out_of_band, level.hindi_share)


class ModelPicker:
    """Lets a self-hosted model choose among the approved forms of a line (it is shown them numbered and answers
    with a number). Whatever it answers, `choose_line` shows only an exact approved form."""

    SYSTEM = ("तुम रवि हो, एक तेलुगु दोस्त। नीचे दी गई मंज़ूर पंक्तियों में से अभी के लिए सबसे ठीक पंक्ति का नंबर चुनो। "
              "नई पंक्ति मत लिखो। जवाब सिर्फ़ JSON में: {\"choice\": नंबर}")

    def __init__(self, provider):
        self.provider = provider
        self.last = None  # the last Completion, for the caller to log

    def __call__(self, line_text: str, context: dict, variants: tuple = ()) -> str:
        from .llm import parse_json

        options = [line_text, *variants]
        listing = "\n".join(f"{i}. {o}" for i, o in enumerate(options))
        self.last = self.provider.complete([{"role": "system", "content": self.SYSTEM},
                                            {"role": "user", "content": f"दृश्य {context.get('scene_id')}:\n{listing}"}],
                                           max_tokens=20, temperature=0.0)
        obj = parse_json(self.last.text, ("choice",)) if self.last.ok else None
        try:
            return options[int(obj["choice"])] if obj else ""
        except (ValueError, TypeError, IndexError):
            return ""
