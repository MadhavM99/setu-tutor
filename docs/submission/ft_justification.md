# Fine-tuning Raju (task 10): no-go, and why

**Decision: we did not fine-tune.** The go/no-go check on the training data failed, so no QLoRA run was started. The
bottleneck was **training data we could verify**, not compute: the planned run on a free Colab T4 would have taken
about 15–20 minutes. Every number below comes from `reports/ft_data.json`, `reports/ft_split.json` or
`reports/ft_eval.json`.

## What we planned

We planned to fine-tune Gemma-3-1B-it (4-bit QLoRA) to do Raju's job: take a correct Telugu sentence and write it
back with exactly one Hindi-habit error of a named rule. Sections 1–3 of `drafts/ft_model_choice.md` explain the base
model choice (Telugu tokenizer fertility 1.97 tokens/word; 20/20 exact copies of bank sentences).

Training pairs (correct, wrong) had to pass a **research validator**, because the app's leak filter can only certify
the ~29 approved planted sentences and cannot label new data. The validator (`setu/research/ft_data.py`) accepts a
pair only if:
- both sentences are plain Telugu and use only bank vocabulary;
- they differ in one short region, which is the rule's known error marker;
- the pair is not a frozen evaluation case or a near-duplicate of one (normalised edit distance ≤ 0.3).

On the 29 frozen pairs the validator accepts 29/29, so recall is 1.00. This is partly circular, because the allowed
edit shapes come from those pairs. On 869 synthetic negatives it accepts 2 (0.2%). Both are HI-TE-006 pairs, a rule
we leave out of training.

## The go/no-go bar, fixed before generating any data

All four checks must hold. HI-TE-006 is left out of training by design, because whether మేము or మనం is right depends
on the meaning, and a sentence pair cannot show the meaning. So the per-rule check is read **without HI-TE-006**, a
reading decided before any data was generated. The strict reading, which counts HI-TE-006, can never be met, and the
report keeps it as `go_strict`.

| Check | Result | Needed | Met |
|---|---|---|---|
| Rules covered (of 14 trainable HI→TE rules) | 2 | ≥ 12 | no |
| Accepted pairs | 23 | ≥ 200 | no |
| ≥ 10 pairs for each frozen-case rule (without HI-TE-006) | only HI-TE-002 has 10 or more (21) | every rule | no |
| Validator recall on frozen pairs | 29/29 | ≥ 0.9 | yes |

**Result: no-go.** The strict reading (`go_strict`) is also not met.

## Where the data went: the yield funnel

We asked gemini-3.5-flash for 8 pairs per call, with the rule explanation and the bank vocabulary in the prompt.

| Stage | Removed | Left |
|---|---|---|
| Model calls attempted | | 57 |
| Calls with a reply (39 were `429` free-tier quota errors) | 39 | 18 |
| Candidate pairs from those 18 calls | | **144** |
| Plain Telugu, bank vocabulary only | 73 | 71 |
| Exactly one edit, of this rule's error | 13 | 58 |
| Not a frozen case or a near-duplicate of one | 4 | 54 |
| Not a duplicate of an accepted pair | 31 | **23** |

Each rejected pair is counted once, at the first check it fails. The calls that replied covered only three rules:
HI-TE-001 (8 calls, 0 pairs accepted), HI-TE-002 (8 calls, 21 pairs) and HI-TE-003 (2 calls, 2 pairs).

**We did not loosen the validator after seeing this.** Widening the vocabulary, the error markers or the
near-duplicate threshold would have raised the yield. But it would also have changed the definition of a "correct"
training pair after looking at the data, and the extra pairs could not have been checked by anyone native.

## What this tells us

1. **The bottleneck is verifiable data, not compute.** Training a 1B model with QLoRA costs minutes on a free GPU.
   What we could not get was a few hundred pairs that we can *show* are correct and contain exactly one error of the
   intended rule. Half the candidates (73 of 144) failed the first check, mostly because they used Telugu words outside the 173-word
   bank vocabulary. Even
   with that vocabulary in the prompt, a strong model does not stay inside a small learner vocabulary. Where it does
   (HI-TE-002), it repeats itself: 31 of the 144 candidates duplicated an accepted pair.
2. **Some rules resist the pair format.** HI-TE-001 (yes/no questions) got 0 of its 64 candidates accepted. The model
   writes the error as "క్యా + changed verb ending", which is two edits, and short question sentences fall within
   0.3 edit distance of the frozen cases. HI-TE-006 cannot be judged from the form at all.
3. **The free tier cannot produce a dataset.** The key allowed 20 requests per day per model, and the run hit that
   limit after 18 successful calls.
4. **The app already gets Raju's errors right without a model.** It shows the approved bank sentence whenever no
   model draft passes the strict filter. A tuned model could only add variety, and only on the cases where its draft
   passes that filter.

## What we report instead (task 17)

Task 17 was pre-registered before any data was generated (`drafts/ft_model_choice.md`, section 4). Without a tuned
model, it compares the **untuned** Gemma-3-1B-it (run locally) with prompted gemini-3.5-flash on the 29 frozen
cases. Both use the same prompt and are scored by the app's strict filter. See `reports/ft_eval.md`, which also
shows HI-TE-006 separately as the "untrained rule".

On the primary set, **untuned Gemma passes the strict filter on 7/29 = 0.24 [0.12, 0.42]**. The prompt shows the
bank's wrong form, so a pass mostly means the model copied it exactly. Gemma failed in three main ways:
- not exactly one error of the rule (15 cases);
- writing the correct form, which leaks the answer (7 cases);
- words outside the vocabulary (3 cases).

Prompted gemini-3.5-flash on the same cases passes **21/29 = 0.72 [0.54, 0.85]**. It passed on 14 cases where
Gemma failed, and never the reverse (exact McNemar p < 0.001). That gap is what fine-tuning was meant to close. It
stays open because the training data could not be built.

## What would make fine-tuning viable

- **More bank items written and approved by teachers**, so the bank itself is the training source and no model
  generation is needed.
- **A native speaker reviewing a larger vocabulary**, so the validator's vocabulary check can be widened honestly.
- **A billed API key** with a few hundred calls for generation, plus a native spot-check of about 30 accepted pairs.

The code is ready for this. `ft_data.py` resumes generation where it stopped, `ft_split.py` makes a seeded train/val
split that a unit test checks for overlap with the frozen cases, and `ft_eval.py` has a slot for the tuned condition.
