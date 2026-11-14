# Guide for Native Telugu Annotator (Batch A — 50 Examples)

Thank you for contributing your linguistic expertise to **SETU**, a research project focused on second-language learning for Hindi speakers learning Telugu.

---

## 1. Context and Purpose

In this learning environment:
- An AI classmate named **Raju** is learning Telugu alongside human learners. Raju frequently makes grammatical mistakes caused by negative transfer from his native Hindi habits.
- A learner observes Raju's sentence and submits their own Telugu sentence (`learner_correction`).
- **Your role:** As a native Telugu speaker, evaluate the learner's submitted sentence directly against two primary criteria:
  1. **Meaning:** Does it accurately convey the intended communicative meaning in `hindi_meaning`?
  2. **Grammar & Naturalness:** Is it linguistically sound, acceptable, and natural Telugu?

*Note on Raju's sentence:* The `classmate_sentence` is provided only as conversational background so you know what prompted the learner. Do **not** treat Raju's sentence as a rigid template that the learner was required to edit word-by-word. Any valid, natural Telugu expression of the `hindi_meaning` is acceptable.

---

## 2. Evaluation Sheet Columns

The evaluation file contains the following columns:

| Column Name | Description | Annotator Action |
|---|---|---|
| `row_id` | Unique 8-character identifier for this example | **Do not modify or delete** |
| `batch` | Identifies this group as `A` | **Do not modify** |
| `target_language` | Always `Telugu` for this batch | **Do not modify** |
| `hindi_meaning` | The intended communicative meaning in Hindi | Read carefully to understand the intended message |
| `classmate_sentence` | Raju's initial sentence containing an error | Background context showing what prompted the learner. **Do not use this as a mechanical reference template.** |
| `learner_correction` | **The learner's submitted Telugu sentence** | **This is the text you evaluate against `hindi_meaning` and Telugu linguistic norms.** |
| `label` | **Your linguistic judgment** | **Must be one of: `correct`, `partial`, `wrong`, `unsure`** |
| `note` | Observations, register, or dialect notes | Optional but encouraged for nuance or context |

---

## 3. Allowed Labels and Evaluation Guidelines

For each of the 50 rows, assign exactly **one** of the following four labels in lowercase in the `label` column:

### 1. `correct`
Select `correct` when the learner's sentence accurately, naturally, and grammatically conveys the `hindi_meaning` in Telugu.

Please apply the following linguistic principles:
- **Pronoun Omission (Pro-drop):** In Telugu, subject pronouns (such as నేను, మీరు, అతను) are frequently omitted when verb inflection makes the subject clear. Do not penalize a sentence solely because a subject pronoun is omitted, **provided** the sentence still unambiguously and correctly communicates the intended meaning. If the omission creates ambiguity or distorts the meaning, evaluate accordingly or use `note`.
- **Spoken vs. Formal Registers:** Everyday spoken Telugu often uses contracted or conversational forms (e.g., వస్తున్నా alongside formal వస్తున్నాను). Rather than enforcing rigid textbook grammar, judge whether the sentence is naturally accepted in contemporary everyday Telugu. If a sentence is acceptable only in a specific dialect or casual register, mark it `correct` and note the register in the `note` column.
- **Devanagari Transliteration (Script Bridge):** Some beginning learners who cannot yet type Telugu script type Telugu words using Devanagari letters (e.g., `मनं वॆळ्तुन्नां` for `మనం వెళ్తున్నాం`). If a sentence is written in Devanagari script, inspect whether the underlying Telugu words, grammar, and sounds are accurately represented. If the Telugu phrasing is accurate despite the script, it should be accepted as `correct`. If the transliteration distorts the Telugu words or grammatical suffixes, mark `partial` or `wrong` based on the severity of the distortion.
- **Short Answers and Elliptical Responses:** In dialogue, learners sometimes provide concise phrases or omit words that are understood from context. Judge whether the shortened response constitutes an acceptable communicative answer that preserves the core intended meaning. Do not mark an answer `wrong` simply because it is concise, unless critical grammatical or semantic elements are missing.

### 2. `partial`
Select `partial` when the learner's sentence successfully communicates the core thought of the `hindi_meaning`, but contains a minor linguistic imperfection that does not entirely disrupt comprehension:
- **Minor orthographic slip:** A minor spelling slip or a single omitted or misplaced vowel symbol (matra), while the intended word remains easily recognizable.
- **Minor grammatical or lexical slip:** An omitted or extra non-essential word, or a minor inflectional discrepancy, while the primary grammatical structure and core vocabulary are sound.
- **Slight semantic divergence:** The sentence is grammatically well-formed in Telugu, but slightly alters a secondary nuance of the `hindi_meaning` while keeping the central message intact.

### 3. `wrong`
Select `wrong` when the learner's sentence fails to function as an acceptable Telugu expression of the `hindi_meaning`:
- **Semantic failure:** The sentence conveys a meaning substantially different from, or contradictory to, the `hindi_meaning`.
- **Severe ungrammaticality:** The sentence contains major syntactic or morphological violations that make it broken, unintelligible, or unnatural to a native speaker.
- **Uncorrected erroneous form:** The sentence retains an ungrammatical or incorrect structure that fails to convey the intended thought in acceptable Telugu.
- **Incoherent fragment:** The submission is an isolated, incomplete fragment that does not constitute a viable communicative utterance.

### 4. `unsure`
Select `unsure` when:
- The sentence is genuinely ambiguous, and multiple plausible interpretations exist.
- You are uncertain whether the phrasing is acceptable without broader pragmatic context.

---

## 4. Annotator Rules and CSV Handling

To preserve research validity and data integrity, please follow these instructions:

1. **Blind and Independent Evaluation:**
   - There are no hidden "app-approved answers" you are expected to match. 
   - Judge each sentence independently based on your native speaker intuition of Telugu acceptability.
2. **Preserve Sheet Structure:**
   - Edit **only** the `label` column and the `note` column.
   - Do **not** edit, rename, reorder, or delete any `row_id`.
   - Do **not** modify the text in `hindi_meaning`, `classmate_sentence`, or `learner_correction`.
3. **Completeness:**
   - All 50 rows in Batch A must have an explicit label. Do not leave any row blank.
   - Use only the four exact lowercase labels: `correct`, `partial`, `wrong`, or `unsure`.
4. **Use of the `note` Column:**
   - Please add brief remarks whenever you encounter spoken dialectal variations, alternative phrasings, or when explaining why you marked an item `partial` or `unsure`.
5. **File Saving Format:**
   - Save your completed work as a **CSV file with UTF-8 encoding** (to avoid corrupting Telugu characters).
   - Return the completed file under a new filename (for example, `teacher_label_sheet_batch_a_completed.csv`) so the original unlabelled template remains untouched.
