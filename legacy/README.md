# Setu Tutor — learn Telugu from Hindi by teaching Raju

A Hindi speaker learns Telugu step by step, and from day one proves it by correcting **Raju**,
an AI classmate who is always one step behind the learner.

**Models write, rules decide.** A language model may draft sentences and hints; only deterministic
rules (the checker, the leak filter) decide what is correct, what is shown, and what Raju knows.

## Learning order (never start with grammar)
| Level | Learner learns | Raju's mistakes |
|---|---|---|
| 0 · Letters | Telugu letters as twins of Devanagari (క = क) | misreads a letter |
| 1 · Words | shared Sanskrit words, numbers, greetings, false friends | uses a false friend |
| 2 · Phrases | ready-made phrases for one situation (auto, shop) | mixes up a phrase |
| 3 · Rules | grammar contrasts (no "है" in "यह किताब है") | the Hindi-speaker grammar mistake, then follow-up questions |

The course is a book (`data/hi-te/course.json`): **chapters → modules → numbered lessons.** A module has 2–4
lessons (1.1, 1.2, 1.3: cards → drill → check), then **"🧒 Raju को आपकी मदद चाहिए" (1.4)**: Raju makes mistakes
only on that module's lessons, you fix them and answer his follow-ups. When Raju knows every lesson of the
module, the next module opens. Later, when you start to forget a lesson, Raju forgets it too, and a short
**🔁 revision** comes first. The side panel shows the whole course with ✅ ▶️ ⬜ 🔒 and Raju's progress.

## How this follows the paper (v8)
| Paper | Here |
|---|---|
| §5 Hindi head start: letters as Devanagari twins, shared words, false friends | अध्याय 1 अक्षर, अध्याय 2 शब्द |
| §5 Scenes (auto stand, mess, landlord) | अध्याय 3: 🛺 ऑटो स्टैंड · 🍛 मेस · 🏠 मकान-मालिक · 👨‍👩‍👧 घर-परिवार · 📚 कॉलेज (`data/hi-te/course.json`) |
| §6.2 Error bank: 15 HI→TE rules, 29 items, planted error + accepted forms + patterns | `data/hi-te/rules.json` (the team's bank + Hindi explanations and key ideas), loaded as level-3 lessons |
| "A rule reaches the classmate only after the learner was taught it and answered once" | each rule lesson: sentence cards → practice → check; Raju only at the module's end |
| §5 Exchange: classmate writes the planted error and asks why → learner fixes → checker → coach hint → answer after 2nd miss → classmate learns (k = 1) | 🧒 Raju lesson: his Telugu sentence with the Hindi-speaker mistake → you write the right sentence (Hindi keyboard OK) → **"पर ऐसा क्यों?"** → you explain → he hands you the rule's other sentence |
| Self-explanation scored on the rule's key idea | `checker.check_why`: keyword groups per rule, no model |
| §4 Leak filter, Token Miss Rate = 0 (Eq. 1) | `leakfilter.check_line`: every Telugu word Raju writes is one you have met, or a word of his planted sentence; no word of the right answer |
| ~20% no-error turns | planner spot checks; a one-sentence rule's follow-up is a correct sentence |
| Coach: L1 hint, checked to contain no answer | 👩‍🏫 दीदी: hint after a wrong fix; never a word of the right sentence |
| Native friend in the scene, level-checked | 👨 रवि opens each rule lesson in its scene (`setu/friend.py`); only your words + the lesson sentence |
| Spacing: the classmate forgets when you are due | unchanged (`raju.forget` at recall < 0.5) → 🔁 दोहराओ |
| Only the checker changes what Raju knows; learner text never in Raju's prompt | unchanged; tested |
| Gemma 3 12B on vLLM | `SETU_LLM_URL` (own server) or Gemma 4 on Google AI Studio (`GEMINI_API_KEY`) |

Not built yet (paper marks them exploratory or later): mirror mode (TE→HI rules are still empty in the bank),
the "own sentence" part, predict-then-check, speech, the matched-error-example and normal-tutor conditions.
**All Telugu in the bank is `draft_unverified` and needs a native speaker's review before learners use it.**
To try the rules straight away: Settings → "सीधे यहाँ से शुरू करो" → अध्याय 3.

## Build steps (each one is approved before it is committed)
- [x] 1 · Skeleton: plan, data types, one sample unit, tests
- [x] 2 · Level 0 letters: 24 small units (1–4 letters each, partners together: short/long, plain/breathy), one card per letter with shape, mnemonic, example word and picture; a drill that stays on each letter until it is right (a miss shows the card again; 3 misses → marked weak, Raju asks it first); checker
- [x] 3 · Level 1 words: numbers, first words, question words, Hindi-twin words (+ం), false friends; type Telugu with a Hindi keyboard
- [x] 4 · Raju core: notebook (unknown → learning → taught → forgotten), follow-ups, 5-check leak filter, planner, forgetting, saved progress; optional model server
- [x] 5 · Grammar rules from the team's bank, in scenes, with fix → why → other sentence (paper §5)
- [~] 6 · Language model: Raju's lines and reactions written by Gemma (Google AI Studio or own server) ✓; still to do: coach hints
- [~] 7 · App: terminal ✓, web app (Streamlit) ✓, Docker ✓; still to do: approved letter pictures, model server in the demo

All Telugu content is `draft_unverified` until a native speaker reviews it.

## Try it in the terminal
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python -m setu.cli                    # learner "me"; progress saved in runs/me.json
    python -m setu.cli --learner priya    # a second learner with their own Raju
    python -m setu.cli --list             # list the units
While playing: type your answer · `/ok` = Raju's line is correct · `/skip N` = jump N days (watch Raju forget) ·
`/status` = your memory and Raju's notebook · `/q` = quit.

## Web app
    pip install -r requirements.txt
    streamlit run app.py                  # opens http://localhost:8501
Pages: **सीखो और Raju को सिखाओ** (cards → drill → check → Raju), **Progress · Raju की कॉपी**,
**अक्षर-पुस्तक** (look back at any card), **Teacher queue** (answers the checker could not judge).
The sidebar picks the learner and has demo controls (jump days to watch Raju forget, reset a learner).
The page always redraws from the saved progress, so a refresh or a restart continues where you were.

**Adding a page for a new step:** write `web/<name>.py` (use `from setu.web import tutor, learner, style, card`)
and add one `st.Page(...)` line to `PAGES` in `app.py`. All teaching logic stays in `setu/`, never in a page.

**Deploy:** `docker build -t setu .` then `docker run -p 8501:8501 -v setu-data:/data setu`.
Progress is kept in the `/data` volume (`SETU_STORE`). To use the model server for Raju's lines add
`-e GEMINI_API_KEY=<key>  (or -e SETU_LLM_URL=http://<gpu-box>:8000/v1 -e SETU_LLM_API_KEY=<secret>)`; without it, fixed sentences are used.

## Pictures for letters (planned with step 7)
Each card has an `image` field, empty for now; the terminal shows the emoji instead. The plan for real pictures:
the **letter is drawn by code from a real Telugu font** (an image model would draw it slightly wrong, and the
learner would memorise the wrong shape); an **image model draws only the object around it** (ర as an apple
with a stem); code puts the two together; a person approves it; only then is `image` set
(e.g. `images/L0-07-b.png` under `data/hi-te/`). Made once per letter, offline, never live per learner.

## Memory hooks: drafted by AI, approved by a person
Every letter card has a shape description, a mnemonic, an example word the learner already knows from Hindi, and a
picture. The first set was drafted with an AI and checked against the rendered letters; all are `draft_unverified`
until a native speaker approves them. For new units, the model server drafts hooks into a separate review file:

    python scripts/draft_hooks.py L0-07          # writes data/hi-te/drafts/L0-07.json (never overwrites)

A reviewer copies the good ones into the unit file. Learners never see unreviewed model text in lessons.

## AI: Raju talks (Gemma)
**The model writes, the rules decide.** Raju's mistake comes from the bank and every verdict comes from the
checker. The model writes **what Raju says**:
1. **his line:** the planned claim ("ఖ = क") in his own words, as a playful 12-year-old from Lucknow
   (cricket, samosas, his dadi…), different every time;
2. **his reaction after you answer:** thanks when you fix him, a celebration when he finally knows, or
   confusion when your answer is wrong, without ever giving the answer away.

Every model line passes the leak filter before it is shown. For his line, five checks: unseen Telugu, exactly
one claim, unknown unit, answer leak, explanation. For his reaction: no answer while confused, no repeating his
old mistake, no other letters, no explaining. A rejected line goes back to the model with the reasons; after
that, a fixed sentence is used. **What the learner types is never put into a prompt.**

**👩‍🏫 Didi, the AI teacher** (`setu/didi.py`): on the cards and in the drill you can ask her a doubt
("🙋 दीदी से पूछो"); after a miss in the drill she gives a hint about the shape or the trick, never the answer.
She answers only from this lesson's cards (and letters already learned). Rules check every answer: Hindi only,
only letters you have been shown, never a wrong letter–sound pair, a hint never contains the answer. If she
can't pass, she says she'll ask the teacher, and the question goes to the Teacher queue. She is silent during
the scored check and while you teach Raju.

**Raju sticks to the lesson:** the model gets the lesson cards Raju "studied" (title, tip, shapes) and must
make a believable mix-up from them, thinking aloud like a classmate ("दीदी ने कहा था नीचे वाली लकीर साँस
है… पर…"). On a mistake turn the right answer is blanked from everything the model sees. His follow-up questions
are written the same way, and every line still passes the 5 checks.

**The model also teaches every card** (`setu/aids.py`), inside guards:
- **✨ AI memory trick:** Gemma gets only the card's checked facts (letter, sound, the shape description verified
  against the real font, example word) and writes a new trick. Rules reject it if it pairs the letter with a
  wrong sound, uses any other Telugu letter, leaves out the letter or its sound, or is not short Hindi.
- **✨ AI picture:** Google's image model ("Nano Banana", same key) draws only the example word's object
  (lotus for కమలం) and is told to write no text. **The letter itself is never drawn by a model.** The app writes
  it on top of the picture from the real font. Gemma then looks at the picture: stray writing or a wrong object
  means it's redrawn once, otherwise not shown.
- **If no image model works with your key** (no free tier, retired model), **your Gemma draws the picture as SVG
  shapes.** `aids.clean_svg` rejects any drawing with text, scripts or links, so the AI can never draw a letter.
- **The picture is shown right after you answer a letter correctly** (drill, check, Raju): picture + the real
  letter + 'క = क · కమలం = कमल'. Before the answer it would give it away.
- Pictures for the rest of a lesson are made in the background; Settings → '🖼️ चित्र जाँचो' tests one and
  shows Google's reply for each model, '🎨 … सारे चित्र अभी बनाओ' makes a whole module in advance.
- Both are made once per card, kept in `<store>/ai/`, and reused for every learner. Learners can ask for
  another trick or picture, or 👍 a trick; a teacher approves ✅ or rejects ❌ each on the Teacher page.
- `SETU_IMAGE_MODEL` (comma list) picks the image model; the first that works with your key is kept.
  `SETU_IMAGES=off` turns pictures off.

**Quickest: Gemma 4 on Google AI Studio (free key, no GPU).** Get a key at aistudio.google.com, then

    export GEMINI_API_KEY=<key>
    export SETU_LLM_MODEL=gemma-4-26b-a4b-it     # default; or gemma-4-31b-it (bigger, slower)
    streamlit run app.py

(Gemma 3 is no longer served on the Gemini API since May 2026, so Gemma 4 is used there.)

**Own GPU server (deployment):** any OpenAI-compatible server, e.g. vLLM:

    vllm serve google/gemma-3-12b-it --api-key <secret> --port 8000
    export SETU_LLM_URL=https://<your-gpu-server>:8000/v1
    export SETU_LLM_MODEL=google/gemma-3-12b-it
    export SETU_LLM_API_KEY=<secret>

`SETU_LLM_TIMEOUT` (default 12 s) caps every call. If both are set, `SETU_LLM_URL` wins. With neither, or if the
model is slow or down, fixed sentences are used, so a demo never stalls. The sidebar shows which one is
active; lines written by the model are marked "✨ AI ने लिखा"; every turn logs `model` or `template`, the
rejected drafts and the number of model calls. `scripts/draft_hooks.py` uses the same settings.

## Run tests
    pip install -r requirements.txt
    python -m pytest -q
