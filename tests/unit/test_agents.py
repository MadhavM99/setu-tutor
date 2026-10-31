"""Self-hosted model client and the three agents, with a mock transport/provider only (mid-submission sprint;
P-MODEL-01, P-COST-04, P-ARCH-03/07/08, P-CLS-03..08, F-COACH)."""
import json

import httpx
import pytest

from setu.agents import classmate, coach, friend, llm
from setu.domain import checker, leakfilter

ITEM = checker.ItemKey(item_id="HI-TE-001-a", target_script="telugu", correct_form="నువ్వు వస్తావా",
                       wrong_form="క్యా నువ్వు వస్తావు")
OTHER = checker.ItemKey(item_id="HI-TE-002-a", target_script="telugu", correct_form="నేను వెళ్ళను",
                        wrong_form="నేను నహీ వెళ్తాను")
SEEN = frozenset({"క్యా", "నువ్వు", "వస్తావు", "వస్తావా", "నేను", "వెళ్ళను", "నహీ", "వెళ్తాను"})


def ctx(turn="planted"):
    return leakfilter.Context(item=ITEM, turn=turn, seen_words=SEEN, unknown_rule_items={"HI-TE-002-a": OTHER})


def reply(content, usage=None):
    return httpx.Response(200, json={"model": "qwen-test", "choices": [{"message": {"content": content}}],
                                     "usage": usage or {"prompt_tokens": 50, "completion_tokens": 9}})


# ---------------------------------------------------------------- client


def test_the_client_refuses_hosted_endpoints_unless_explicitly_allowed_and_https():
    with pytest.raises(llm.NotLocal):
        llm.OpenAICompatible("https://api.groq.com/openai/v1", "m")
    with pytest.raises(llm.NotLocal):
        llm.OpenAICompatible("http://api.example.com/v1", "m", allow_hosted=True)
    assert llm.OpenAICompatible("https://api.groq.com/openai/v1", "m", allow_hosted=True).hosted
    assert llm.is_local("http://localhost:1234/v1") and llm.is_local("http://192.168.1.5:11434/v1")


def test_a_hosted_key_is_sent_as_a_bearer_header_and_never_appears_in_errors():
    seen = []

    def handler(request):
        seen.append(request.headers.get("authorization"))
        return httpx.Response(401, json={"error": "bad key"})
    c = llm.OpenAICompatible("https://api.groq.com/openai/v1", "m", allow_hosted=True, api_key="sk-secret-123",
                             transport=httpx.MockTransport(handler)).complete([{"role": "user", "content": "x"}])
    assert seen[0] == "Bearer sk-secret-123" and "sk-secret" not in (c.error or "") and c.error.endswith("401")


def test_from_environment_reads_the_hosted_settings(monkeypatch):
    monkeypatch.setenv("SETU_LLM_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("SETU_LLM_MODEL", "meta-llama/llama-3.3-70b-instruct")
    monkeypatch.setenv("SETU_LLM_API_KEY", "k")
    monkeypatch.delenv("SETU_LLM_ALLOW_HOSTED", raising=False)
    with pytest.raises(llm.NotLocal):
        llm.OpenAICompatible.from_environment()
    monkeypatch.setenv("SETU_LLM_ALLOW_HOSTED", "1")
    assert llm.OpenAICompatible.from_environment().hosted


def test_the_client_records_usage_latency_and_strips_reasoning():
    t = httpx.MockTransport(lambda r: reply('<think>secret</think>{"sentence": "x"}'))
    c = llm.OpenAICompatible("http://localhost:1234/v1", "qwen", transport=t).complete([{"role": "user",
                                                                                      "content": "hi"}])
    assert c.ok and c.text == '{"sentence": "x"}' and c.prompt_tokens == 50 and c.completion_tokens == 9
    assert c.latency_ms >= 0 and len(c.request_hash) == 64


def test_the_client_retries_then_reports_the_error():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(500)
    c = llm.OpenAICompatible("http://localhost:1234/v1", "qwen", retries=2,
                             transport=httpx.MockTransport(handler)).complete([])
    assert not c.ok and "HTTPStatusError" in c.error and len(calls) == 3


def test_structured_output_needs_every_key():
    assert llm.parse_json('blah {"sentence": "a"} blah', ("sentence",)) == {"sentence": "a"}
    assert llm.parse_json('{"other": 1}', ("sentence",)) is None and llm.parse_json("no json", ("x",)) is None


def test_from_environment_is_off_without_a_url(monkeypatch):
    monkeypatch.delenv("SETU_LLM_URL", raising=False)
    assert llm.OpenAICompatible.from_environment() is None


# ---------------------------------------------------------------- Raju


def sent(s):
    return json.dumps({"sentence": s}, ensure_ascii=False)


def test_a_valid_planted_proposal_is_used():
    t = classmate.propose(llm.MockProvider([sent("క్యా నువ్వు వస్తావు")]), ctx(), rule_title="सवाल",
                          hindi_meaning="तुम आओगे?", bank_sentence="క్యా నువ్వు వస్తావు")
    assert (t.text, t.source, len(t.drafts)) == ("క్యా నువ్వు వస్తావు", "model", 1)


@pytest.mark.parametrize("bad,reason", [("నువ్వు వస్తావా", "ANSWER_LEAK"), ("మీరు ఎక్కడ", "OOV"),
                                        ("నేను వెళ్ళను", "UNKNOWN_RULE_CORRECT"), ("Sure, here is", "WRONG_SCRIPT")])
def test_leaks_unseen_words_unknown_rules_and_assistant_text_fall_back_to_the_bank(bad, reason):
    p = llm.MockProvider([sent(bad)] * 3)
    t = classmate.propose(p, ctx(), rule_title="सवाल", hindi_meaning="तुम आओगे?", bank_sentence="BANK")
    assert t.text == "BANK" and t.source == "bank" and len(t.drafts) == 3
    assert any(reason in d.reasons for d in t.drafts)


def test_the_tool_method_feeds_the_filter_reasons_back_and_resampling_does_not():
    p = llm.MockProvider([sent("నువ్వు వస్తావా"), sent("క్యా నువ్వు వస్తావు")])
    t = classmate.propose(p, ctx(), rule_title="सवाल", hindi_meaning="तुम आओगे?", bank_sentence="BANK")
    assert t.source == "model" and "ANSWER_LEAK" in p.calls[1][-1]["content"]
    p2 = llm.MockProvider([sent("నువ్వు వస్తావా"), sent("క్యా నువ్వు వస్తావు")])
    classmate.propose(p2, ctx(), rule_title="सवाल", hindi_meaning="तुम आओगे?", bank_sentence="BANK",
                      method="resample")
    assert "ANSWER_LEAK" not in p2.calls[1][-1]["content"]


def test_prompt_only_makes_one_draft_and_a_no_error_turn_needs_the_correct_form():
    p = llm.MockProvider([sent("మీరు ఎక్కడ")])
    t = classmate.propose(p, ctx(), rule_title="", hindi_meaning="", bank_sentence="BANK", method="prompt_only")
    assert len(p.calls) == 1 and t.source == "bank"
    ok = classmate.propose(llm.MockProvider([sent("నువ్వు వస్తావా")]), ctx("no_error"), rule_title="",
                           hindi_meaning="", bank_sentence="BANK")
    assert ok.source == "model"


# ---------------------------------------------------------------- coach


def test_a_hint_without_the_answer_is_used_and_a_leaky_or_latin_one_is_not():
    good = coach.hint(llm.MockProvider(['{"hint": "सवाल का निशान वाक्य के अंत में देखिए।"}']), ITEM,
                      rule_title="सवाल", approved=("generic", None), wrong_sentence="క్యా నువ్వు వస్తావు")
    assert good.source == "model" and good.text.startswith("सवाल")
    for bad in ('{"hint": "लिखिए నువ్వు వస్తావా"}', '{"hint": "Write vastava"}', "not json",
                '{"hint": "निषेध (మరియు కాదు అన్న భావం) देखिए"}'):
        h = coach.hint(llm.MockProvider([bad]), ITEM, rule_title="सवाल", approved=("l1_rule", "मंज़ूर इशारा"),
                       wrong_sentence="క్యా నువ్వు వస్తావు")
        assert (h.text, h.source) == ("मंज़ूर इशारा", "approved") and h.rejected


def test_without_a_model_the_coach_uses_the_approved_or_generic_hint():
    assert coach.hint(None, ITEM, rule_title="", approved=("generic", None), wrong_sentence="").source == "generic"


# ---------------------------------------------------------------- friend


def test_the_friend_model_can_only_pick_an_approved_line():
    line = friend.ApprovedLine("ఎక్కడికి వెళ్ళాలి?")
    for answer, source in (('{"choice": 0}', "model"), ('{"choice": 7}', "bank"), ("ఎక్కడికి పోతావు", "bank")):
        pick = friend.ModelPicker(llm.MockProvider([answer]))
        out = friend.choose_line(line, pick(line.text, {"scene_id": "s"}), seen_words=set(),
                                 scene_words={"ఎక్కడికి", "వెళ్ళాలి"}, learner_band="L5")
        assert out.text == "ఎక్కడికి వెళ్ళాలి?" and out.source == source
