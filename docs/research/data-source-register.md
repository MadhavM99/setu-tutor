# Data-source register

Every external source is listed with its licence, permitted use, provenance and limits [X-DSR]. **Status** is `verified` (licence read and recorded), `to-check` (licence not yet confirmed) or `n/a`. Nothing marked `to-check` may enter learner-facing content or a commercial build. The `data_source` table mirrors this file.

| ID | Source | What we use it for | Size / scope | Licence / permission | Status | Limits and notes |
|---|---|---|---|---|---|---|
| DS-01 | Native speakers (team reviewers, teachers) | Rule validity, variants, naturalness, bands, audio | 2 per language + a third | Reviewer agreement form; audio consent | to-check (forms to write) | Small panel → κ reported [R-03] |
| DS-02 | Krishnamurti & Gwynn 1985, *A Grammar of Modern Telugu* | Verify Telugu contrasts (polar -ā, two "we", verbless X-is-Y, ఇది for "she", negative verb, -కి, కోసం, -రు with మీరు, participle relatives) | Citations only | Copyright; cite, do not reproduce | n/a (citation) | Example sentences are not copied into the product |
| DS-03 | Chinnappa 1978 (PhD thesis) | Proxy evidence for TE→HI difficulty (gender 78%, ने 76%, complex sentences 73%) | Survey percentages | Citation | n/a | School students, 1978, difficulty not error counts → `proxy` only |
| DS-04 | Telangana "simple Telugu" textbooks: Tenepalukulu (I–V), Vennela (VI–X) | Order of topics and words for bands | Order only | Government publication; **no copying of sentences without permission** | to-check | FW-P24 needs written permission |
| DS-05 | IndicCorp v2 (Doddapaneni et al. 2023) | Telugu word frequencies → top 1,000–2,000 | Frequency counts only | Check the dataset licence (CC-type, as published) | to-check | Web text; frequency ≠ learner usefulness, so it is crossed with textbook order |
| DS-06 | Kanojia et al. 2020, cognates and false friends | ~150 shared words; false-friend flags | ~150 pairs | Check the LREC dataset licence | to-check | Pairs need native review |
| DS-07 | IndicGEC 2025 (BHASHA), Telugu | Checker robustness only (no false accept, no false reject of variation) | ~1,000 native pairs | Check the shared-task licence | to-check | **Not** Hindi-speaker learner evidence; quality issues (Vajjala 2025) |
| DS-08 | LTRC Hindi–Telugu parallel corpus (Mujadia & Sharma 2022) | How contrasts are realised in translation; contrast examples | ~700K pairs; a few hundred simple pairs used | **Commercial use must be confirmed** | to-check | Translation ≠ learner error |
| DS-09 | IndicXlit / Aksharantar (Madhani et al. 2023) | Romanised → Telugu normalisation | Pretrained model | Check the model licence | to-check | Never treated as automatically correct |
| DS-10 | LTRC Telugu morphological analyser; Stanza (Qi et al. 2020) | Word forms in the checker | Evaluate on 50 sentences first | Check the licences (Stanza: Apache-2.0) | to-check | Until evaluated, unseen forms → unsure |
| DS-11 | WALS (Dryer & Haspelmath 2013), Grambank (Skirgård et al. 2023) | Typology leads | Features coded for both languages | CC-BY (as published) | to-check | Leads only; noisy Telugu coding |
| DS-12 | HiLearners (Behera & Saluja 2025) | Contrast-validity test (Dravidian-L1 group) | Public release lacks L1 labels | Check the licence; ask the authors for labels | to-check | Dravidian languages unnamed → no Telugu claim |
| DS-13 | Native recordings | Audio for the top 100 items | 100 clips | Speaker consent + rights record | to-check | Speaker review |
| DS-14 | AI4Bharat IndicConformer (ASR), Indic Parler-TTS | Speech extension | Models | Check the model licences | to-check | Evaluate WER vs Whisper; never assume TTS is native |
| DS-15 | Whisper (Radford et al. 2023) | ASR baseline | Model | MIT | to-check | Baseline only |
| DS-16 | Gemma 3 12B (and 4B for dev / low cost) | Classmate, coach, friend (self-hosted) | Model | Gemma terms of use | to-check | Model swappable; per-direction bake-off |
| DS-17 | Sarvam-M | **Model comparison only**, not a content source | Model | Check the licence | to-check | Never used to generate content |
| DS-18 | Anonymised, consented adult learner writing (both directions) | Observed errors; TransferErrorBench | When permitted | Institutional permission + consent | to-check | No identifiable text to any external service |
| DS-19 | Teacher-marked test cases | Stage A suite, ~150, 30% held out | ~150 | Team-owned | verified (team) | Kept apart from build data |
| DS-20 | Team rule bank and content (setu-tutor, LMA repo) | Draft rules and items, letters, lexicon | 25 rules / 49 items + 45 units | Team-owned; **Claude-drafted, unreviewed** | verified (ownership) / content unreviewed | Credit the LMA repo authors; record team consent (ADR-0001) |
| DS-21 | V&S Publishers 2015, *Learn Telugu through Hindi* | Prior-art reference for the script bridge | Citation | Copyright | n/a | Not copied |
| DS-22 | Google AI Studio (Gemini, Gemma 4, image models) | **Removed from runtime.** Optional offline drafting of non-learner content (e.g. hook ideas), with teacher review | — | Google terms | n/a | Never receives learner text (D3) |
