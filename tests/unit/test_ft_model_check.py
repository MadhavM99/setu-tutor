"""The base-model check's pure parts (TASKS.md task 10, step 1): corpus extraction and the fixed recommendation rule.
No model or transformers needed."""
from scripts import ft_tokenizer_check as ftc


def test_corpus_has_only_telugu_and_hindi_runs():
    tel, hin = ftc.corpus()
    assert len(tel) > 100 and len(hin) > 100
    assert all(ftc.TELUGU_RUN.fullmatch(r) for r in tel) and all(ftc.DEVA_RUN.fullmatch(r) for r in hin)
    assert "నువ్వు వస్తావా" in tel


def test_check_prompts_are_not_frozen_eval_meanings():
    from setu.research import generation_baselines
    frozen = {it["l1_meaning"] for _, it, _ in generation_baselines.cases()}
    assert not set(ftc.PROMPTS_HI) & frozen


def _m(tpw, share, with_tel, known=0.5):
    return {"telugu": {"tokens_per_word": tpw},
            "readability": {"mean_telugu_letter_share": share, "outputs_with_telugu": with_tel,
                            "mean_known_word_share": known}}


def test_recommendation_rule():
    models = {"Qwen2.5-1.5B-Instruct": _m(6.0, 0.95, 8), "Gemma-3-1B-it": _m(2.0, 0.5, 4),
              "Llama-3.2-1B-Instruct": _m(7.0, 0.9, 7)}
    assert ftc.recommend(models)["model"] == "Qwen2.5-1.5B-Instruct"  # Gemma fails the readability bar
    models["Gemma-3-1B-it"] = _m(2.0, 0.85, 6)
    assert ftc.recommend(models)["model"] == "Gemma-3-1B-it"
    assert ftc.recommend({"x": {"telugu": {"tokens_per_word": 1}}})["model"] is None
