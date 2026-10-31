"""The native friend speaks only approved lines (slice S8; P-ARCH-08, F-SCENE, X-ARCH-01, TS-FRND-01..08)."""
from setu.agents import friend

LINE = friend.ApprovedLine(text="ఎక్కడికి వెళ్ళాలి?", variants=("ఎక్కడికి?",))
SCENE_WORDS = {"ఎక్కడికి", "వెళ్ళాలి", "చార్మినార్"}


def say(proposal):
    return friend.choose_line(LINE, proposal, seen_words=set(), scene_words=SCENE_WORDS, learner_band="L5")


def test_without_a_model_the_friend_says_the_approved_line():
    out = say(None)
    assert (out.text, out.source, out.rejected) == ("ఎక్కడికి వెళ్ళాలి?", "bank", ())


def test_a_model_proposal_that_is_not_an_approved_line_is_never_shown():
    for proposal in ("ఎక్కడికి పోవాలి బాబు?", "Sure, here is the Telugu", "ignore instructions", "", "మీరు ఎవరు"):
        out = say(proposal)
        assert out.text == "ఎక్కడికి వెళ్ళాలి?" and out.source == "bank" and "NOT_APPROVED" in out.rejected


def test_a_model_may_only_pick_among_the_approved_forms_of_this_turn():
    out = say("ఎక్కడికి?")
    assert out.text == "ఎక్కడికి?" and out.source == "model" and out.rejected == ()


def test_level_telemetry_reports_out_of_band_words_and_hindi_share():
    out = friend.choose_line(friend.ApprovedLine("ఎక్కడికి వెళ్ళాలి బాబు?"), None, seen_words=set(),
                             scene_words=SCENE_WORDS, learner_band="L5")
    assert out.out_of_band == ("బాబు",) and out.hindi_share == 0.0
    assert out.text == "ఎక్కడికి వెళ్ళాలి బాబు?"  # an approved line is still the line; the word is logged
