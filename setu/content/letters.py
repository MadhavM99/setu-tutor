"""L0 script content: the modern Telugu letters in varnamala order with their Devanagari twins (X-LAD-L0, P8b-04).

Generated from the normaliser's verified Unicode tables, so every twin matches the bridge learners type through.
Archaic letters (ఌ, ఴ) are left out. Letters new to Hindi readers are flagged: short ఎ and ఒ (Hindi has only the
long vowels), ళ and ఱ. Labels and notes are a development draft: every letter needs two native-speaker approvals
before learners see it (`learner_letter` view).
"""
from setu.domain.normalise import TELU_TO_DEVA

GROUPS = (
    ("vowels", "स्वर", "అఆఇఈఉఊఋఎఏఐఒఓఔ"),
    ("ka", "क-वर्ग", "కఖగఘఙ"),
    ("ca", "च-वर्ग", "చఛజఝఞ"),
    ("tta", "ट-वर्ग", "టఠడఢణ"),
    ("ta", "त-वर्ग", "తథదధన"),
    ("pa", "प-वर्ग", "పఫబభమ"),
    ("others", "य से ह", "యరఱలళవశషసహ"),
)
LABELS = {"ఎ": "ए (छोटा)", "ఏ": "ए (लंबा)", "ఒ": "ओ (छोटा)", "ఓ": "ओ (लंबा)"}
NEW_FOR_HINDI = {
    "ఎ": "छोटा ए। हिंदी में सिर्फ़ लंबा ए होता है।",
    "ఒ": "छोटा ओ। हिंदी में सिर्फ़ लंबा ओ होता है।",
    "ళ": "जीभ ऊपर मोड़कर बोला जाने वाला ल। हिंदी में आम तौर पर नहीं होता।",
    "ఱ": "पुराना ज़ोरदार र। आजकल ज़्यादातर र जैसा बोला जाता है।",
}
SOURCE = "Unicode Telugu/Devanagari tables via setu.domain.normalise (normaliser-1); notes drafted by the team"


def build_letters() -> list[dict]:
    letters, order = [], 0
    for group, group_hi, chars in GROUPS:
        for ch in chars:
            order += 1
            letters.append({
                "id": f"te-letter:{ch}",
                "telugu": ch,
                "devanagari": TELU_TO_DEVA[ch],
                "twin_label_hi": LABELS.get(ch, TELU_TO_DEVA[ch]),
                "kind": "vowel" if group == "vowels" else "consonant",
                "group": group,
                "group_hi": group_hi,
                "varnamala_order": order,
                "new_for_hindi": ch in NEW_FOR_HINDI,
                "note_hi": NEW_FOR_HINDI.get(ch),
                "review_status": "draft",
                "provenance": [{"source": SOURCE}],
            })
    return letters
