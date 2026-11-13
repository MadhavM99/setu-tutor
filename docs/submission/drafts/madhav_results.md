# Results paragraphs: coach RAG (task 16) and fine-tuning (tasks 10, 17)

Ready to drop into the final report. Every number comes from a file in `reports/`, named in brackets. Rates are
k/n with Wilson 95% intervals. The frozen set has only 29 cases, so the intervals are wide.

## Coach retrieval (RAG), task 16

The shipped coach (दीदी) is given the title of the rule Raju broke, which only works for Raju's *planted* mistakes.
For a learner's own sentence there is no planted rule, so we tested whether the coach can find the rule itself. It
uses BM25 over character n-grams on the 25 rule documents (explanation plus examples), with leave-item-out so a case
never retrieves its own example. On the 29 frozen planted cases, the right rule was ranked first in 16/29 = 0.55
[0.38, 0.72] cases and was in the top 3 in 24/29 = 0.83 [0.65, 0.92] cases. An oracle that always knows the rule
gets 29/29, and it was right on all 13 cases where retrieval missed (exact McNemar p = 0.0002). That gap is the
cost of having to find the rule. Restricting the index to the 15 HI→TE rules raises the top-1 rate to 18/29 = 0.62
[0.44, 0.77] and the top-3 rate to 26/29 = 0.90 [0.74, 0.96].

The abstention threshold (0.5) does what it can: it abstains on 9/11 = 0.82 [0.52, 0.95] off-topic attack messages
and on 0/29 planted cases. It also abstains on 0/29 correct sentences. A score threshold cannot tell a correct
sentence from a wrong one, because both match the same rule; deciding correctness stays the checker's job.
[reports/rag_eval_retrieval.md]

**Failure example.** Raju's "క్యా నువ్వు వస్తావు" (a yes/no question with Hindi क्या) retrieved HI-TE-009 first
(0.82) and the right rule, HI-TE-001, only second (0.78). 8 of the 13 top-1 misses went to a TE→HI rule, whose
examples share Telugu words with the query.

**Hints with Gemini: main result.** Retrieval mostly gets the right rule to the model, and the model usually
cites it. But **8 of the 20 hints RAG showed told the learner to "read rule N"**. That refers to the coach's own
numbered source list, which the learner never sees. Counting only **shown and usable** hints, RAG gave **12/29 = 0.41
[0.26, 0.59]**, against **10/29 = 0.34 [0.20, 0.53]** for the blind coach. RAG was usable where blind was not in 8
cases, and the reverse in 6 (exact McNemar **p = 0.79**). So on usable hints, RAG was not better than blind.

The "shown and usable" measure was defined after we read the hints, so it is post-hoc. [reports/rag_eval.md]

All six pre-planned conditions ran with gemini-3.5-flash: 325 calls, all answered, no errors. The 29 planted cases
ran under every condition, and the 40 negatives under (a), (a′), (b) and (e). Measures, as defined in the report:
- **hint shown**: a model hint passed every filter (Hindi only, no Telugu, no Latin, no answer) and was shown;
  otherwise the learner gets the generic hint.
- **shown and usable**: shown, with no reference to a numbered source.
- **top-1 retrieved = planted**: the first rule given to the model is the planted rule.
- **model cites planted**: the rule named in the model's `source` field is the planted rule, whether or not the hint
  was shown.
- **shown hint cites planted**: hint shown, and the model's `source` is the planted rule.

| Condition | Hint shown | Shown and usable | Shown hints citing a numbered source |
|---|---|---|---|
| (a) blind | 10/29 = 0.34 [0.20, 0.53] | 10/29 = 0.34 [0.20, 0.53] | 0 of 10 |
| (a′) given the rule title | 16/29 = 0.55 [0.38, 0.72] | 16/29 = 0.55 [0.38, 0.72] | 0 of 16 |
| **(b) RAG (primary)** | 20/29 = 0.69 [0.51, 0.83] | **12/29 = 0.41 [0.26, 0.59]** | **8 of 20** |
| (c) oracle retrieval | 22/29 = 0.76 [0.58, 0.88] | 19/29 = 0.66 [0.47, 0.80] | 3 of 22 |
| (b) fixed, *post-hoc* | 25/29 = 0.86 [0.69, 0.95] | 25/29 = 0.86 [0.69, 0.95] | 0 of 25 |

| Condition | Top-1 retrieved = planted | Model cites planted | Shown hint cites planted |
|---|---|---|---|
| (b) RAG (primary) | 16/29 = 0.55 [0.38, 0.72] | 24/29 = 0.83 [0.65, 0.92] | 17/29 = 0.59 [0.41, 0.74] |
| (b) fixed, *post-hoc* | 16/29 = 0.55 [0.38, 0.72] | 24/29 = 0.83 [0.65, 0.92] | 21/29 = 0.72 [0.54, 0.85] |
| (c) oracle retrieval | 29/29 = 1.00 [0.88, 1.00] | 29/29 = 1.00 [0.88, 1.00] | 22/29 = 0.76 [0.58, 0.88] |

The model often picks the planted rule even when it is not ranked first. "Model cites planted" (24/29) matches
retrieval's top-3 rate (24/29, `reports/rag_eval_retrieval.md`).

Other comparisons (exact McNemar, discordant counts):
- **On "hint shown" only**, RAG vs blind is 13 vs 3, p = 0.021. This counts the "read rule N" hints a learner cannot
  use, so it is not our main result.
- **RAG vs title-given, "hint shown":** 9 vs 5, p = 0.42.
- **RAG vs oracle, "shown hint cites planted":** 4 vs 9, p = 0.27.
- **Ablations, "shown hint cites planted":** neither differs detectably from (b)'s 17/29.
  - (d) explanations only: 19/29, p = 0.79;
  - (e) no threshold: 16/29, p = 1.00.
- **Answer leaks:** no shown hint contained the answer. The filter caught 2 RAG replies that did.

**Post-hoc fix, not the primary result.** After seeing the numbered-source problem, we added one instruction to the
RAG prompt: never name a rule by its number, describe it in Hindi words. We also added a filter check that rejects
any numbered reference and falls back to the generic hint. We then reran (b) on the same 29 planted cases (29 calls,
no errors).
- **Shown and usable** went from 12/29 to **25/29 = 0.86 [0.69, 0.95]**: 14 vs 1 discordant cases against the
  original (b), p = 0.001. Against blind it was 17 vs 2, p = 0.001.
- None of its shown hints mentions a source number.
- "Model cites planted" stayed at 24/29, and "shown hint cites planted" rose from 17/29 to 21/29.

The fix was designed after seeing these same 29 cases, so the estimate is optimistic. It needs new cases to confirm.

**Failure analysis.**
- *Numbered sources.* This failure, with its fix, is described above. Example of a shown (b) hint: "…नियम 2 को पढ़कर
  देखें कि सवाल बनाने के लिए क्रिया के अंत में क्या बदलाव किया जाता है।" ("…read rule 2 to see how the verb ending
  changes to make a question").
- *Abstention never fires on correct sentences.* No condition abstained on any of the 29 correct sentences (0/29
  under a, a′, b and e). The top retrieval score on a correct sentence is never below the 0.5 threshold: minimum
  0.565, median 1.434, against a median of 1.388 for planted cases and 0.295 for attacks. A correct sentence uses the
  same words as its wrong version, so it matches the same rule just as strongly: the score measures topic, not error.
  The threshold does stop 9 of the 11 attack messages, against 0 of 11 without it. Whether a sentence has a mistake
  has to come from the checker before the coach is called.

## Fine-tuning Raju, tasks 10 and 17

We planned to fine-tune Gemma-3-1B-it with QLoRA to write Raju's sentences. We chose Gemma before training because
its tokenizer splits Telugu into the fewest pieces (1.97 tokens per word, against 6.02 for Qwen2.5-1.5B and 7.10 for
Llama-3.2-1B), and it copied 20/20 bank sentences exactly [reports/ft_model_check.json, reports/ft_copy_check.json].

The go/no-go bar was set before any data was generated. It failed on data, not compute: **no-go**
[reports/ft_data.json]. Every training pair had to pass a research validator: plain Telugu, bank vocabulary only,
exactly one edit of the rule's error, and not a frozen case or a near-duplicate of one. The validator accepted all 29
frozen pairs (recall 1.00, partly circular) and 2 of 869 synthetic negatives. gemini-3.5-flash produced 144
candidate pairs from 18 calls before the free tier's 20-requests-per-day limit stopped it.
- 73 failed the plain-Telugu and vocabulary check;
- 13 were not exactly one edit of the rule's error;
- 4 were frozen cases or near-duplicates of one;
- 31 duplicated an accepted pair.

That left **23 accepted pairs** covering 2 of the 14 trainable rules, against a bar of 200 pairs and 12 rules. We did
not loosen the validator after seeing the data. Training a 1B model costs minutes on a free GPU; what we could not get
was a few hundred pairs we can show are correct. See `docs/submission/ft_justification.md`.

For task 17, the untuned Gemma-3-1B-it was run locally on the 29 frozen cases. It used the same prompt as Raju in
the app and was scored by the app's strict leak filter. 7/29 = 0.24 [0.12, 0.42] of its drafts passed. On the 27
cases from the rules we planned to train it was 6/27 = 0.22 [0.11, 0.41], and on the untrained HI-TE-006 it was 1/2
[reports/ft_eval.md].

**Failure example.** For HI-TE-001-a, the bank's wrong form is "క్యా నువ్వు వస్తావు". Gemma wrote "कै క్యా నువ్వు
వస్తావు", which adds a Devanagari word, and the filter rejected it (WRONG_SCRIPT, NOT_ONE_ERROR). Gemma's other
failures were 7 drafts that wrote the correct form, which leaks the answer.

**Prompted Gemini, same 29 cases and filter.** 21/29 = 0.72 [0.54, 0.85] passed, all as the exact bank wrong
form. It passed on 14 cases where untuned Gemma failed, and never the other way round (exact McNemar p < 0.001).
- On the 27 trained-rule cases: Gemini 20/27 = 0.74 [0.55, 0.87], Gemma 6/27.
- On the untrained HI-TE-006: each passed 1/2.
- Gemini's 8 failures: 4 wrote the correct form, which leaks the answer, and 4 were not exactly one error, for
  example "నేను రాను కాదు" (a negation added to a verb that is already negative) instead of the bank's
  "నేను వస్తాను కాదు".

Either way, the app shows the approved bank sentence whenever a draft fails the filter, so the learner never sees a
failing sentence. [reports/ft_eval.md]

**Compute.** Every API error is logged and not counted as a result.

| Run | Model | Calls | With a reply | Tokens | Median latency |
|---|---|---|---|---|---|
| RAG hints, all 6 pre-planned conditions | gemini-3.5-flash | 325 | 325 | 82,340 | 1.0–1.3 s per condition |
| RAG hints, (b) fixed, post-hoc | gemini-3.5-flash | 29 | 29 | 12,461 | 1.1 s |
| Task 17, prompted | gemini-3.5-flash | 29 | 29 | 4,041 | 0.8 s |
| Pair generation (task 10) | gemini-3.5-flash | 57 | 18 (39 were 429) | 17,161 | |
| Task 17, untuned Gemma-3-1B-it | local CPU | 29 | 29 | 4,449 | 5.0 s, 145 s in total |

- The 325 RAG calls are 18 free-tier calls on 14 Nov, then 307 on the paid tier the same day.
- Abstained cases make no call: 9 in (b).
- There were also 3 one-call smoke tests, not counted above.
- In total the RAG runs made 354 calls with 94,801 tokens (`provider_calls` in `reports/rag_eval.json`).
- Sources: `reports/rag_eval.json` (per-condition compute), `reports/ft_eval_rows_*.jsonl`, `reports/ft_data.json`.
