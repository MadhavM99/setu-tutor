# Teacher label sheet (M-16)

Built by `python -m setu.research.label_sheet` (seed fixed, so it rebuilds the same rows).

- `teacher_label_sheet.csv`: **send this to the labeller.** 145 rows, shuffled, random ids. It shows no checker verdict and no reference answer.
- `teacher_label_key.csv`: **do not send.** The checker's verdict and the attempt type for each row, joined on `row_id` when computing κ.

Batch A (50 rows, all Hindi→Telugu) is for the native Telugu speaker. Batch B (95 rows) is the rest, including 41 Telugu→Hindi rows that need a Hindi speaker.

## Instructions for the labeller

A Hindi-speaking learner is learning Telugu. A classmate wrote `classmate_sentence`, which is meant to say `hindi_meaning` but contains a mistake. The learner typed `learner_correction` to fix it.

Fill the `label` column with exactly one of:

| label | meaning |
|---|---|
| `correct` | A natural, correct sentence for the meaning. Other script is fine (e.g. Telugu typed in Devanagari letters) |
| `partial` | The main mistake is fixed, but there is a small slip (a spelling slip, a missing or extra word) |
| `wrong` | The mistake is still there, it means something else, or it is not a sentence for this meaning |
| `unsure` | You can't tell, or several readings are possible |

Judge the learner's sentence on its own. Don't try to guess what the app would say. Use `note` for anything worth explaining, for example "also correct, dropping నేను is fine".
