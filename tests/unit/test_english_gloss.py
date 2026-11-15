from setu.web.english import ENGLISH, english
from setu.web.pictures import PICTURES


def test_every_pictured_word_has_an_english_gloss():
    assert set(PICTURES) <= set(ENGLISH)


def test_the_gloss_can_be_turned_off(monkeypatch):
    assert english("అవును") == "yes"
    monkeypatch.setenv("SETU_ENGLISH_GLOSS", "0")
    assert english("అవును") is None
