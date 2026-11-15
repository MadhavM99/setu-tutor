# UI additions (branch `faviana-noronha`): what they are, how they match the spec, what is not done

Status of everything here: **built, tested, not evaluated.** No simulator models it and no real learner has used it.
Every Telugu word shown has had at most one review, by a bilingual team member (not independent), and the new Hindi strings are drafts.

## What was added

| Feature | Where | Notes |
|---|---|---|
| Learning-path map (L0–L5, "you are here") | home and `/ladder` (`setu/web/path.py`, `_path.html`) | built from the existing `ladder()` data and Madhav's L0–L5 bands; no new levelling logic |
| Word pictures | intro and feedback cards, match game (`setu/web/pictures.py`) | 27 of 28 words, inline SVG, Hindi alt text; never on a question about the same word |
| Match-the-pairs game | `/learn/match` (`setu/domain/matching.py`, `routes_match.py`) | meanings or pictures; checked by `check_choice`; updates the card schedule only |
| Listen and say-it | `static/js/voice.js`, `_voice.html` | browser voice; **behind flags, off by default** (below) |
| Step label, bigger targets, celebration | lesson shell, CSS | the celebration is not animated under `prefers-reduced-motion` |

## How it matches the spec

- **Speech flags (architecture.md §7, P-ARCH-13).** The spec keeps ASR and TTS behind `speech_input` and
  `tts_synthetic`, off until their gates pass. They are now `SETU_SPEECH_INPUT` and `SETU_TTS_SYNTHETIC`, default off.
  With a flag off, its controls and `voice.js` are not in the page (tests: `test_speech_is_off_by_default…`,
  `test_each_speech_flag_turns_on_only_its_own_controls`). Browser voices carry `data-voice="synthetic"`, never "native"
  (X-SPEECH-03).
- **Egress (architecture.md §6).** The spec allows only the self-hosted model and speech hosts. Browser speech
  recognition is a browser feature, not our server, but in Chrome it sends audio to Google. That is why it is off by
  default and why the report must say so. Browser text-to-speech may also use a network voice on some devices.
- **X-INPUT-08 (record the aids).** The picture version of the match game records `["choices", "illustration"]`
  (the schema allows `illustration`); the meaning version records `["choices"]`.
- **X-INPUT-09 / 12 (recognition is not recall).** The game uses `check_choice` (kind `recognition`) and writes a card
  review only, with no skill evidence, so it cannot teach Raju or move a learner's level.
- **X-INPUT-05 / 06.** Options come only from the approved-word views, and every control is Hindi (Hindi lint: 0
  violations).
- **E-15 (WCAG 2.2 AA, ≥ 18 px base, self-hosted fonts, keyboard-only flow).** Base size is 18 px and the fonts are
  self-hosted (existing). Checked on the demo app with axe-core 4.10 (WCAG 2.0/2.1/2.2 A and AA plus best practice) at
  390 px and 1280 px on 8 pages: the only open finding is the demo banner outside a landmark (demo-only, existed before
  this branch). Fixed on this branch: contrast of the "soon" path stages (opacity, now a dashed node). Also checked:
  the whole match round can be answered with Tab, Space and Enter (3 px focus outline), no horizontal scroll at 320 px,
  no running animation under `prefers-reduced-motion`.

## Bug found and fixed on the way

The progress page returned a 500 error when a learner's next step was a Telugu word group (the demo learner's case).
My earlier fix wrapped Telugu names in `<span lang="te">`, and the catalog treated the tag name as Latin script.
`Catalog.get_rich` (template helper `t_rich`) checks only the text a reader sees. Regression test:
`test_the_ladder_names_a_word_as_the_next_step_and_still_renders` (fails without the fix, passes with it).

## Not done, and who should look

1. **Memory Assistant overlap.** The spec has a Memory Assistant subsystem (F-MEM, task 4.9) for visual aids, with
   teacher review of every aid and metric M-59 (Hindi alt text **and** an audio alternative on 100% of shown aids).
   The pictures here are a separate, hand-drawn set. They have Hindi alt text but no audio description in Hindi and no
   teacher review. Kushal should decide whether they fold into F-MEM or are labelled as demo-only.
2. **Native audio.** `data-audio` accepts recorded files, which the spec prefers; none exist yet.
3. **Demo banner landmark.** Moving the banner into `<main>` would clear the last axe finding. It is in `base.html`
   and was not touched here.
4. **The two levelers are different things.** Madhav's `setu/domain/leveler.py` gives curriculum bands L0–L5 and drives
   the planner and the ladder (the path map uses it). The sentence leveler in the LMA repo
   (`FavianaNoronha/lma---reverse-learning-tutor`, `setu/leveler.py`, A1–B2) scores one sentence's difficulty, is not
   wired into setu-tutor, and is barely above the majority baseline (exact 0.694 vs 0.633, 49 items). Cite it in the
   report as a separate prototype with that result. Porting it into `setu/research/` is about 30 minutes if wanted.
5. **The simulators do not model any of this.** Do not claim learning gains from voice, pictures or the match game.
