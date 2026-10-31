"""The agents inside the running app, with a scripted MockProvider standing in for the self-hosted model
(mid-submission sprint). The model proposes; the filters decide; every call is logged; the bank is the fallback."""
import json

from .test_correction import CORRECT, WRONG, advance_to, answer, client, one, rule_bank  # noqa: F401  (fixture)


def provider(raju_sentence, hint_text):
    from setu.agents.llm import MockProvider

    def reply(messages):
        system = messages[0]["content"]
        if "राजू" in system:
            return json.dumps({"sentence": raju_sentence(messages)}, ensure_ascii=False)
        return json.dumps({"hint": hint_text}, ensure_ascii=False)
    return MockProvider(reply)


def bank_wrong(messages):
    text = messages[1]["content"]
    return next(w for w in WRONG if w in text)  # the model writes the planted sentence it was shown


def test_a_planted_sentence_from_the_model_is_shown_and_logged(engine, rule_bank):  # noqa: F811
    c, learner = client(engine)
    c.app.state.llm = provider(bank_wrong, "आख़िरी शब्द को ध्यान से देखिए।")
    page = advance_to(c, "planted")
    ex = one(engine, "SELECT e.id, e.source, e.task FROM exchange e JOIN session s ON s.id = e.session_id WHERE "
                     "s.learner_id = :l AND e.kind = 'correction' ORDER BY e.created_at DESC LIMIT 1", l=learner)
    assert ex.source == "model" and ex.task["raju"]["source"] == "model"
    call = one(engine, "SELECT agent, model, error FROM model_call WHERE exchange_id = :e", e=ex.id)
    assert (call.agent, call.model, call.error) == ("classmate", "mock-for-tests", None)
    wrong = next(w for w in WRONG if w in page)
    hinted = answer(c, page, typed=wrong).text
    assert "आख़िरी शब्द को ध्यान से देखिए।" in hinted  # the coach's hint passed the leak check
    coach_call = one(engine, "SELECT error FROM model_call WHERE exchange_id = :e AND agent = 'coach'", e=ex.id)
    assert coach_call.error is None
    done = answer(c, hinted, typed=WRONG[wrong]).text
    assert "जाँचने वाले का फ़ैसला:" in done and "मॉडल ने लिखा" in done


def test_an_invented_sentence_and_a_leaky_hint_never_reach_the_learner(engine, rule_bank):  # noqa: F811
    c, learner = client(engine)
    c.app.state.llm = provider(lambda m: "ఇది కొత్త వాక్యం బాబు", "ऐसे लिखिए: " + " ".join(sorted(CORRECT)))
    page = advance_to(c, "planted")
    assert "కొత్త" not in page
    ex = one(engine, "SELECT e.id, e.source FROM exchange e JOIN session s ON s.id = e.session_id WHERE "
                     "s.learner_id = :l AND e.kind = 'correction' ORDER BY e.created_at DESC LIMIT 1", l=learner)
    assert ex.source == "bank"
    assert one(engine, "SELECT count(*) AS n FROM model_call WHERE exchange_id = :e AND error LIKE 'rejected:%'",
               e=ex.id).n == 3
    wrong = next(w for w in WRONG if w in page)
    hinted = answer(c, page, typed=wrong).text
    assert "ऐसे लिखिए" not in hinted and WRONG[wrong] not in hinted.replace(wrong, "")
