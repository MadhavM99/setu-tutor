"""English glosses shown under a Telugu word on the intro and feedback cards (a presentation aid only).

The app's interface is Hindi, and the word bank stores Hindi glosses only (the database refuses Latin text there), so
these live here, not in the catalog or the database. They are never shown on a question about the same word, so
they cannot give away an answer. On by default; set SETU_ENGLISH_GLOSS=0 to turn it off.
"""
import os

ENGLISH = {
    "ఒకటి": "one", "రెండు": "two", "మూడు": "three", "నాలుగు": "four", "ఐదు": "five", "ఆరు": "six",
    "ఏడు": "seven", "ఎనిమిది": "eight", "తొమ్మిది": "nine", "పది": "ten",
    "నమస్కారం": "hello / greetings", "ధన్యవాదాలు": "thank you", "అవును": "yes", "ఏమిటి": "what",
    "ఎక్కడ": "where", "ఎప్పుడు": "when", "ఎవరు": "who", "ఎంత": "how much", "పుస్తకం": "book",
    "సమయం": "time", "దేశం": "country", "పాఠం": "lesson", "అర్థం": "meaning", "భాగం": "part",
    "అవసరం": "need", "ఉపన్యాసం": "speech / lecture", "చరిత్ర": "history", "ఆలస్యం": "delay",
}


def english(telugu: str) -> str | None:
    if os.environ.get("SETU_ENGLISH_GLOSS", "1") == "0":
        return None
    return ENGLISH.get(telugu)
