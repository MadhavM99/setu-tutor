"""L1 akshara content: vowel signs (gunintalu), ం and ః, double letters and common conjuncts (X-LAD-L1, P8b-04).

Generated from the normaliser's verified Unicode tables, so every Devanagari twin is the letter-by-letter bridge.
Order is sign by sign (one sign across many consonants), so a learner generalises each sign. The rare ఙ ఞ ఱ get no
signs or doubles here. Labels and notes are a development draft: each akshara needs two native-speaker approvals
before learners see it (`learner_akshara`, which also requires every letter in it to be approved).
"""
from setu.domain.normalise import TELU_TO_DEVA

from .letters import GROUPS

VIRAMA = "్"
RARE = set("ఙఞఱ")
CONSONANTS = [ch for group, _, chars in GROUPS if group != "vowels" for ch in chars if ch not in RARE]
# (key, Telugu sign, Hindi name of the sign, note for Hindi readers or None)
SIGNS = (
    ("aa", "ా", "आ की मात्रा", None),
    ("i", "ి", "इ की मात्रा", None),
    ("ii", "ీ", "ई की मात्रा", None),
    ("u", "ు", "उ की मात्रा", None),
    ("uu", "ూ", "ऊ की मात्रा", None),
    ("r", "ృ", "ऋ की मात्रा", None),
    ("e", "ె", "छोटे ए की मात्रा", "हिंदी में यह मात्रा नहीं होती: छोटा ए।"),
    ("ee", "ే", "लंबे ए की मात्रा", None),
    ("ai", "ై", "ऐ की मात्रा", None),
    ("o", "ొ", "छोटे ओ की मात्रा", "हिंदी में यह मात्रा नहीं होती: छोटा ओ।"),
    ("oo", "ో", "लंबे ओ की मात्रा", None),
    ("au", "ౌ", "औ की मात्रा", None),
    ("am", "ం", "अनुस्वार (बिंदु)", "तेलुगु में बिंदु अक्सर अगले अक्षर का नासिक स्वर बनता है, जैसे ‘अम’।"),
    ("ah", "ః", "विसर्ग", None),
)
FAMILY = {key: ("nasal_visarga" if key in ("am", "ah") else "vowel_signs") for key, *_ in SIGNS}
CONJUNCTS = ("క్ష", "త్ర", "ప్ర", "శ్ర", "స్త", "న్న", "మ్మ", "ద్ద", "క్క", "ల్ల", "స్థ", "ష్ట", "ర్మ", "గ్ర")
SOURCE = "Unicode Telugu/Devanagari tables via setu.domain.normalise (normaliser-1); notes drafted by the team"


def twin(telugu: str) -> str:
    return "".join(TELU_TO_DEVA[ch] for ch in telugu)


def _unit(order, telugu, *, kind, family, group, group_hi, letters, note=None):
    return {
        "id": f"te-akshara:{telugu}",
        "telugu": telugu,
        "devanagari": twin(telugu),
        "twin_label_hi": twin(telugu),
        "kind": kind,
        "family": family,
        "group": group,
        "group_hi": group_hi,
        "letters": letters,
        "order": order,
        "note_hi": note,
        "review_status": "draft",
        "provenance": [{"source": SOURCE}],
    }


def build_aksharas() -> list[dict]:
    out, order = [], 0
    for key, sign, name_hi, note in SIGNS:
        for c in CONSONANTS:
            order += 1
            out.append(_unit(order, c + sign, kind="sign", family=FAMILY[key], group=f"sign-{key}",
                             group_hi=name_hi, letters=[c], note=note))
    doubles = [c + VIRAMA + c for c in CONSONANTS]
    for d in doubles:
        order += 1
        out.append(_unit(order, d, kind="double", family="doubles", group="double", group_hi="दोहरा अक्षर",
                         letters=[d[0]], note="एक ही अक्षर दो बार: नीचे छोटा रूप जुड़ता है।"))
    for cj in CONJUNCTS:
        if cj in doubles:
            continue
        order += 1
        out.append(_unit(order, cj, kind="conjunct", family="conjuncts", group="conjunct", group_hi="संयुक्त अक्षर",
                         letters=[cj[0], cj[2]], note="दूसरा अक्षर पहले के नीचे छोटे रूप में जुड़ता है।"))
    return out
