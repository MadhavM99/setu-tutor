# Slides: coach RAG and fine-tuning Raju (Madhav, tasks 9, 10, 16, 17)

Six slides, about 5 minutes. A teammate can present these without me: the speaker notes say what to say, and every
number points to its report file.

---

## Slide 1: Can दीदी find the rule herself?

- Today the coach is **given** the rule Raju broke, which works only for Raju's planted mistakes
- Learners make their own mistakes, and then nobody knows the rule
- So we tried **retrieval**: find the rule from the sentences, then hint
- Every hint still goes through the same filters: Hindi only, no Telugu, no answer

**Speaker notes.** Our coach gives hints in Hindi. In the shipped app she gets the title of the rule Raju broke on
purpose, which is easy because we planted the error. A learner's own wrong sentence has no planted rule. The
question for task 16 was whether the coach can find the right rule by herself, and whether her hints stay safe.

---

## Slide 2: How retrieval works

- 25 rule documents: explanation and example sentences (15 HI→TE, 10 TE→HI)
- BM25 over character 2–4-grams, so Telugu inflections still match
- Query = Raju's sentence plus the learner's attempt; the rule ID never reaches the model
- Below a score threshold (0.5) she **abstains** and gives a generic hint
- The model must cite which retrieved rule it used, and we check the citation

**Speaker notes.** It is deliberately simple: no embeddings and no new dependencies, and it is deterministic, so the
results reproduce exactly. Character n-grams matter because Telugu adds endings to words. If nothing scores high
enough, the coach does not guess.

---

## Slide 3: Retrieval results (29 frozen cases)

| | top-1 | top-3 |
|---|---|---|
| All 25 rules | 16/29 = 0.55 [0.38, 0.72] | 24/29 = 0.83 [0.65, 0.92] |
| HI→TE rules only | 18/29 = 0.62 [0.44, 0.77] | 26/29 = 0.90 [0.74, 0.96] |
| Oracle (knows the rule) | 29/29 | 29/29 |

- Oracle vs retrieval: 13 vs 0 discordant cases, p = 0.0002
- Threshold 0.5: abstains on 9/11 attack messages and 0/29 planted cases, but also on 0/29 correct sentences

**Speaker notes.** Source: `reports/rag_eval_retrieval.md`. Retrieval finds the right rule in the top 3 most of the
time, but top-1 is only about half. 8 of the 13 misses went to the opposite-direction rules, which share Telugu
words. The threshold rejects off-topic input but cannot tell right from wrong: a correct sentence matches the
same rule as its wrong version. That is the checker's job, not retrieval's.

---

## Slide 4: Hints with Gemini (29 planted cases)

**Main result: on usable hints, RAG was no better than blind**
- RAG got the planted rule to the model, which named it in 24/29 replies (model cites planted)
- But **8 of the 20 hints RAG showed said "read rule N"**, pointing at a source list the learner never sees
- **Shown and usable: RAG 12/29 = 0.41 [0.26, 0.59] vs blind 10/29 = 0.34 [0.20, 0.53]**, 8 vs 6, **p = 0.79**

| | Hint shown | Shown and usable | Shown hint cites planted |
|---|---|---|---|
| (a) Blind | 10/29 | 10/29 | n/a |
| (a′) Given the rule title (shipped) | 16/29 | 16/29 | n/a |
| **(b) RAG (primary)** | 20/29 | **12/29** | 17/29 |
| (c) Oracle retrieval | 22/29 | 19/29 | 22/29 |
| (b) fixed, *post-hoc* | 25/29 | **25/29 = 0.86 [0.69, 0.95]** | 21/29 |

- Post-hoc fix (prompt plus a filter check): 25/29 usable. Optimistic, and needs new cases to confirm
- On "hint shown" only, RAG beats blind 13 vs 3 (p = 0.021), but that counts unusable hints
- Abstention never fired on correct sentences (0/29): the retrieval score measures topic, not error

**Speaker notes.** Source: `reports/rag_eval.md` (the measures are defined at the end of it). 354 Gemini calls, no
errors. The planned RAG condition is our primary result. Retrieval works: the model named the planted rule in 24 of 29
replies. But when we read the hints, 8 of the 20 shown told the learner to "read rule 2", which refers to a list only
the model sees. Counting usable hints only, RAG is 12/29 and blind 10/29, which is not a real difference (p = 0.79).
We then changed one line of the prompt and added a filter check, and reran RAG once: 25 of 29 usable. Say clearly
that this fix was designed after seeing these same cases, so it is optimistic until tested on new cases. On
abstention: the threshold blocks off-topic attacks but never fires on a correct sentence, because a correct sentence
matches the same rule as its wrong version. Spotting the mistake is the checker's job.

---

## Slide 5: Fine-tuning Raju: a no-go, and the funnel

- Plan: QLoRA on Gemma-3-1B-it (fewest Telugu tokens per word, 1.97; copied 20/20 bank sentences exactly)
- The bar, set before any data: ≥ 200 verified pairs, ≥ 12 of 14 rules
- Yield funnel for Gemini-generated pairs:

  **144** candidates → 71 plain Telugu, bank words → 58 one edit of the rule → 54 not near a test case → **23** after duplicates

- 23 pairs and 2 of 14 rules: **no-go**. The validator was not loosened after seeing the data

**Speaker notes.** Source: `reports/ft_data.json` and `docs/submission/ft_justification.md`. The bottleneck was
training data we could verify, not GPU time: training would have taken minutes on a free Colab. Half the candidates
used Telugu words outside our 173-word bank. Rules like yes/no questions produced zero usable pairs. We also hit the
free-tier limit of 20 requests per day. We kept the bar we set beforehand rather than moving it.

---

## Slide 6: The baselines without fine-tuning (task 17)

| Same 29 frozen cases, app's strict filter | Passed |
|---|---|
| Untuned Gemma-3-1B-it (local) | 7/29 = 0.24 [0.12, 0.42] |
| Prompted gemini-3.5-flash | 21/29 = 0.72 [0.54, 0.85] |

- Gemini passed on 14 cases where Gemma failed, never the reverse: **p < 0.001**
- Trained-rule cases: 6/27 vs 20/27. The untrained HI-TE-006: 1/2 each
- Failures: Gemma, not exactly one error (15) and writing the correct form (7). Gemini, the correct form (4) and
  doubled errors (4)

**Speaker notes.** Source: `reports/ft_eval.md`. Pre-registered before training: primary on all 29 cases, secondary
on the 27 cases from trained rules, HI-TE-006 shown separately. A small model without tuning is far behind a
prompted large model, which is the gap fine-tuning was meant to close, and why the data shortfall matters. Whatever
the model does, the app only shows a sentence that passes the strict filter, and otherwise falls back to the
approved bank sentence. So the learner never sees a bad Raju sentence.
