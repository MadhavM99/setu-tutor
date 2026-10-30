"""Shared definitions for authored content (content-and-error-bank.md, data-model.md).

Content files never carry review or approval: validity, lifecycle and approvals change only through the teacher
console, where reviewers are authenticated. Learner-facing fields hold Devanagari or Telugu only.
"""
import hashlib
import json
import re
import unicodedata

RULE_ID = re.compile(r"^(HI-TE|TE-HI)-[0-9]{3}$")
ITEM_ID = re.compile(r"^(HI-TE|TE-HI)-[0-9]{3}-[a-z]$")
DIRECTION_OF_PREFIX = {"HI-TE": "HI->TE", "TE-HI": "TE->HI"}
# The script of the target language (L2) each direction's sentences are written in.
TARGET_SCRIPT = {"HI->TE": "telugu", "TE->HI": "devanagari"}
# The script of the learner's own language (L1), used for meanings, titles and explanations.
L1_SCRIPT = {"HI->TE": "devanagari", "TE->HI": "telugu"}

BANDS = ("L0", "L1", "L2", "L3", "L4", "L5")
EVIDENCE = ("model_predicted", "predicted", "proxy", "observed", "replicated")
IMPORTABLE = {"validity": ("uncertain", "rejected"), "lifecycle": ("draft",), "review_status": ("draft",),
              "variant_status": ("proposed",)}
APPROVAL_KEYS = ("teacher_approved", "speaker_approvals", "reviewers", "reviewed_at", "approvals")

LATIN = re.compile(r"[A-Za-z]")
TELUGU = re.compile(r"[ఀ-౿]")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
SCRIPT_RE = {"telugu": TELUGU, "devanagari": DEVANAGARI}
OTHER_SCRIPT = {"telugu": DEVANAGARI, "devanagari": TELUGU}


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def normalise_sentence(s: str) -> str:
    """NFC, no zero-width characters, single spaces. Used for comparing and de-duplicating forms."""
    s = nfc(s).replace("\u200c", "").replace("\u200d", "").replace("\u200b", "")
    return " ".join(s.split())


def script_of(s: str) -> set[str]:
    found = set()
    if TELUGU.search(s):
        found.add("telugu")
    if DEVANAGARI.search(s):
        found.add("devanagari")
    if LATIN.search(s):
        found.add("latin")
    return found


def canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_of(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode()).hexdigest()


class Issue:
    """A finding about one record. `error`s block import; plain issues import as drafts and block approval."""

    __slots__ = ("code", "detail", "error", "field")

    def __init__(self, code, detail="", field=None, error=False):
        self.code, self.detail, self.field, self.error = code, detail, field, error

    def as_dict(self):
        d = {"code": self.code, "detail": self.detail}
        if self.field:
            d["field"] = self.field
        return d

    def __repr__(self):
        return f"{'ERROR' if self.error else 'issue'}({self.code}{': ' + self.detail if self.detail else ''})"
