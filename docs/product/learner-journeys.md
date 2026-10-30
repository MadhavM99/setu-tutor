# Learner and teacher journeys

All learner-visible text is Hindi (Devanagari). Telugu appears only in Telugu script. The quoted Hindi strings are draft catalog entries, to be reviewed in [`../specs/localisation-hindi-ui.md`](../specs/localisation-hindi-ui.md). Tags: [P] paper · [X] prompt extension · [E] engineering recommendation.

---

## J-1 Beginner (cannot read Telugu) [X-LAD-L0, P8b-04]

1. **Invite link** → "सेतु में आपका स्वागत है".
2. Choose a passphrase. No email or real name is required. [E-08]
3. **Consent** is given in person to the facilitator before the invite is handed out; the app records it automatically and shows no consent screen (ADR-0007). [P-ETH-04]
4. **"क्या आप तेलुगु पढ़ सकते हैं?"**:
   - "बिल्कुल नहीं" starts at L0. The placement diagnostic is skipped and shown later as an option.
   - "थोड़ा-बहुत" goes to J-3.
5. **Script orientation (L0).** A short Hindi explanation: "तेलुगु और देवनागरी के अक्षर एक ही क्रम में चलते हैं…". Then letter pairs (twins) in varnamala order. New letters are flagged: ఎ, ఒ, ళ, ఱ, ంం, and the final vowel. [P8b-04, X-BEG-01]
6. Each letter is practised in four modalities:
   - recognition: see Telugu → type the Hindi letter;
   - recall: hear or see Hindi → type or pick on the Telugu keyboard;
   - visual discrimination: tell confusable pairs apart;
   - decoding: read short syllables.

   There are no options and no word banks. Hints never show the answer. [P-LSP-01, X-EXCH-04]
7. **Session ends** with "आज आपने ये सीखा" and "अगली बार". The "अगली बार" line is a plan, not a score. [X-PERS-08]
8. **Days 2–n.** FSRS reviews come first, then new letters (capped), then the next skills once unlocked by the multi-item rule. [X-PERS-06]
9. The classmate राजू appears only after the threshold number of verified rules is taught. [P-CLS-10, X-CLS-START] Before that, the learner learns first. A small Hindi line explains: "जल्द ही राजू आएगा — वो आपसे सीखेगा।"

## J-2 Returning learner [P-LSP-03]

1. Log in → "आज का अभ्यास (लगभग १५ मिनट)".
2. The session composer orders the work: due reviews, then due rules as re-teaching (the classmate has "forgotten" them), then new items, then own sentences.
3. If the learner was away for long, more reviews and fewer new items are scheduled. The cap is honoured.

## J-3 Placed learner (knows some Telugu) [X-PERS-03]

1. "जाँच लें आप कहाँ से शुरू करें" starts an adaptive diagnostic, about 10–15 minutes.
2. It starts with L2 high-frequency words. Success moves the learner up to L3/L4 items; failure moves them down to L1/L0 skills.
3. A skill counts as passed only when the same multi-item rule is met: at least 2 items, at least 1 production. Passed skills are marked `placed` and scheduled for a confirmation review within 3 days.
4. Result screen: "आप ये कर सकते हैं: … · यहाँ से शुरू करेंगे: … · क्यों: …". No numbers are shown.
5. Any rule passed at placement can be taught to राजू immediately. [P-CLS-10]

## J-4 Review-due learner [P-LSP-03, P8b-01]

1. The tracker predicts learner recall below 0.5 on rule R.
2. The classmate's state for R becomes `forgotten`.
3. In the next session, राजू writes a new sentence that contains R's error. The learner corrects it and explains why, so the review is re-teaching.
4. On a correct fix, R becomes `taught` again. The learner's mastery is updated from that same verdict.
5. Words and chunks due under FSRS appear as cue-free recall prompts (hear or see Hindi → produce Telugu).

## J-5 Reverse-learning exchange (core) [P-SESS-05..12]

1. राजू: "मैंने ये लिखा — सही है?" followed by one Telugu sentence (with the reading aid if it hasn't faded), e.g. `నువ్వు రేపు వస్తావు?`.
2. The learner chooses:
   - "इसमें गलती है → ठीक करके लिखिए": a text box, empty (not pre-filled), with the on-screen keyboard; or
   - "ये वाक्य सही है".
3. **Correct fix:** "बिल्कुल सही।" राजू: "अच्छा! पर ऐसा क्यों?" Every 3rd checked fix asks for a short Hindi explanation, scored on the concept key. [P8b-02]
4. **Wrong or partial:** a Hindi hint without the answer (a type set by the hint ladder). Second miss: the correct sentence is shown plus "इसे एक बार लिखिए" (copy-practice, not counted as mastery evidence).
5. **Unsure:** "इस जवाब को शिक्षक देखेंगे — अभी इसे गिना नहीं गया।" Nothing changes. [P-ARCH-10]
6. **End of every exchange:** the planted error and its correction are shown side by side. [R-13]
7. **No-error turn (about 20%):** a learner who wrongly "corrects" it gets "ये वाक्य पहले से सही था" and a false alarm is logged. [P-SESS-07]

## J-6 Own sentence [P-SESS-04]

1. Prompt in Hindi with a goal: "ऑटो वाले से पूछिए कि क्या वो चारमीनार जाएगा।"
2. The learner types Telugu (or Devanagari letters, which are converted with the conversion disclosed).
3. The checker:
   - accepted form or variant → correct;
   - the planted error type present → wrong, with a hint;
   - an unseen form → unsure, sent to the teacher, with the message "शिक्षक देखेंगे".
4. Copy rate is computed here: does a planted error reappear in the learner's own production? [M-37]

## J-7 Scene with the native friend [X-LAD-L5, P-ARCH-08]

1. "मेस में" with a short Hindi set-up. रवि speaks Telugu lines limited to the learner's known words and band. Unvalidated lines are replaced by approved scene lines. [X-ARCH-01]
2. Turns alternate: comprehension questions (Hindi) and the learner's Telugu reply (production).

## J-8 Teacher [X-TCH]

1. Log in as a teacher → "आज की जाँच".
2. **Unsure queue:** the answer, item, accepted forms and the checker's reason. Actions:
   - "सही मानें" (accept), optionally adding it as an accepted variant pending a second review;
   - "गलत मानें" (wrong), optionally with an error tag;
   - "आंशिक" (partial).

   The resolution goes through OutcomeWriter with an audit record. [X-TCH-04]
3. **Rule review:** form answers (acceptable/natural, category, explanation, band, confidence). Two raters per language. Disagreement goes to a third reviewer. κ is shown per batch. [X-TCH-03]
4. **Class view:** errors per opportunity per rule, false alarms, copy rate, misconceptions. Estimates are visibly separated from observations. [X-TCH-07, X-TCH-10]
5. **Uploads (gated):** anonymised writing → proposed spans and rules. Nothing is published without approval. [X-TCH-06]

## J-9 Study participant (Stage B) [P §8.3]

1. A facilitator creates a participant with a consent record and a background questionnaire. The Latin square assigns rules to conditions A, B and C. [P-EVAL-14]
2. **Pre-test** on all study rules. A ceiling check flags rules the participant already knows. [P8b-11]
3. **Practice:** one condition per block, the same aids and the same time box. [P-EVAL-15/16]
4. **Immediate post-test**, then a **one-week delayed** unaided production test and a **transfer test** on unseen held-out sentences. [P-EVAL-17]
5. SUS, would-use-again, and the second-session question. Data is exported in blinded form for marking. [P-EVAL-18]

## J-10 Mirror (exploratory, flag off) [P-SESS-03]

The learner corrects a **Hindi** sentence carrying a TE→HI error (e.g. मेरा किताब) and explains it in Hindi. It is tagged `mode=mirror` and reported separately.

## J-11 Memory aid and fading (amendment A1) [X-MEM-AID]

1. **New letter ళ (first encounter).** दीदी: "इसे याद रखने का एक तरीका:".
   - The approved aid appears: a text-free illustration with the app-rendered ళ, the Hindi caption from the catalog, and a native recording, plus a minimal pair కళ్ళు / కల్లు.
   - "दूसरा तरीका" shows the next eligible aid.
   - Logged: `presented`, `selected`, `used`.
2. **Recall.** The aid is hidden. The learner hears or sees the Hindi prompt and types the Telugu (cue level 0). Only this attempt can count toward mastery.
3. **Later encounters.** The cue ladder steps down: full aid → image only → no cue. A lapse at level 0 brings back a partial cue once.
4. **Due reviews** never show the aid before the answer. After a lapse, the aid is offered *after* the answer as relearning.
5. **False friend अवसर / అవసరం.** A two-panel contrast story ("यह नहीं — यह"). The lure, the Hindi meaning "मौका", is declared, and answering it is logged as a misassociation.
6. **Teacher.** Reviews drafts in "स्मृति सहायक जाँच" and sees per-aid effect estimates labelled अनुमान, with n.

## Note on J-5 (राजू) — amendment A1 [X-RAJU]

राजू only ever:
- shows one Telugu sentence (model-written within the contract, or from the bank);
- says a fixed Hindi student line.

There is no chat box to राजू. Anything the learner types goes to the checker only.
