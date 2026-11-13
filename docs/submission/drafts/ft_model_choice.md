# Choosing the base model for the Raju QLoRA run (task 10, step 1)

The base model was chosen on 13 Nov 2026, **before any training and before any frozen-set evaluation**. All numbers
below come from `reports/ft_model_check.json` and `reports/ft_copy_check.json`. Nobody native has checked the
model outputs for meaning.

## 1. Tokenizer fertility

This is the number of tokens per word over the 897 distinct Telugu runs in `content/` (1,185 words). Lower is
better.

| Model | Telugu tokens/word | Hindi tokens/word |
|---|---|---|
| Gemma-3-1B-it | **1.97** | 1.45 |
| Qwen2.5-1.5B-Instruct | 6.02 | 3.69 |
| Llama-3.2-1B-Instruct | 7.10 | 2.38 |

## 2. Readability, and the rule we fixed in advance

Each model was asked to translate 8 Hindi sentences (none from the frozen cases) into Telugu. The rule, fixed in the
code before we looked at any output, was: pick the lowest fertility among models whose output is mostly Telugu script
(mean Telugu-letter share ≥ 0.8, and Telugu in at least 6 of 8 outputs).

| Model | Telugu-letter share | Outputs with Telugu | Known-word share |
|---|---|---|---|
| Qwen2.5-1.5B-Instruct | 1.00 | 8/8 | 0.12 |
| Llama-3.2-1B-Instruct | 0.13 | 1/8 | 0.00 |
| Gemma-3-1B-it | 0.22 | 2/8 | 0.13 |

**The rule picked Qwen.** We overrode it because the rule measured the wrong thing: it checked the script, not real
words.
- Qwen's output is Telugu letters, but only 12% of its words are bank words, and the sentences look like noise, for
  example "मौसम अच्छा है" → "ఈ ముందు ప్రభుత్వ సాయుచితం…".
- Gemma mostly echoed the Hindi back. That is an instruction-following failure, which fine-tuning can fix. When it
  did write Telugu, the output looks right to us, but this is unchecked by a native speaker: "यह मेरी किताब है" →
  "ఇది నా పుస్తకం.".
- Translation is also not the fine-tuning task. The task is to **copy a correct sentence with one planted edit**.

## 3. Copy fidelity: the check that matches the task

Each model was asked to repeat 20 correct bank sentences exactly (greedy decoding; none of the sentences are frozen
cases or near-duplicates of one).

| Model | Exact copies (Wilson 95%) | Mean character edit distance |
|---|---|---|
| Gemma-3-1B-it | 20/20 = 1.00 [0.84, 1.00] | 0.0 |
| Qwen2.5-1.5B-Instruct | 17/20 = 0.85 [0.64, 0.95] | 1.7 |

In an exact McNemar test, Gemma was right on 3 pairs where Qwen was wrong, and Qwen was never right where Gemma was
wrong (p = 0.25). So this check **confirms the override**, though n = 20 is too small for the difference to be
significant. Qwen's failures were corrupted letters ("ఇంకొంచెం" → "ఈనోమొంచెం") and one unrelated sentence.

**Decision: Gemma-3-1B-it** (`unsloth/gemma-3-1b-it`, an ungated copy of Google's weights), switchable through
`MODEL_ID` in the notebook. Training uses fp32 compute, because a T4 has no bf16 support, and checks the first batch
for a NaN loss.

## 4. Pre-registration for the task 17 evaluation

**Written 2026-11-13 22:01 IST, before any training-pair generation, any training run, or any model output on the
frozen cases.** It is not changed after results come in. Any departure from it is reported as a departure.

**Training scope.** Fine-tuning covers the 14 HI→TE rules only. The research validator checks Telugu sentences, and
the TE→HI rules are out of scope. HI-TE-006 is left out of training by design, because whether మేము or మనం is right
depends on the meaning, and a sentence pair cannot show the meaning.

**Data go/no-go** (`reports/ft_data.json`, `go_no_go`). Go needs all four of these:
- at least 12 of the 14 trainable rules covered;
- at least 200 accepted pairs;
- validator recall of at least 0.9 on the frozen pairs;
- at least 10 pairs for every HI→TE rule that has frozen cases, **not counting HI-TE-006**.

The strict reading, which does count HI-TE-006, can never be met. It is reported next to the decision as
`go_strict`.

**Evaluation sets.** All are scored with the app's strict `leakfilter.check_sentence`.

| Role | Cases | Why |
|---|---|---|
| **Primary** | All 29 frozen planting cases | The same set as the prompted-Gemini baseline |
| Secondary | The 27 cases from the 14 trained rules | The rules the model was trained on |
| Reported separately | HI-TE-006's 2 cases, labelled "untrained rule" | Not trained, by design |

All 29 frozen cases are HI→TE, so no TE→HI result is reported. TE→HI is marked out of scope.

**Conditions:**
- the tuned model (Gemma-3-1B-it + QLoRA);
- the untuned base model with the same prompt and format;
- prompted gemini-3.5-flash.

**Statistics.** Each rate gets a Wilson 95% interval. Tuned vs base and tuned vs Gemini each get an exact McNemar test
on the primary set.
