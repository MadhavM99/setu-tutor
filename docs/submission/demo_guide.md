# Demo guide

```bash
cd ~/Developer/setu-tutor
scripts/run_demo.sh            # Postgres (Docker) + isolated setu_demo DB + app on http://127.0.0.1:8000
                               # prints a learner and a teacher login (passphrase: डेमो पासवर्ड बारह)
```

Real model (hosted, optional): put these in your shell (never in a file in the repo), then start the demo:

```bash
export SETU_LLM_URL=https://generativelanguage.googleapis.com/v1beta/openai/
export SETU_LLM_MODEL=gemini-3.5-flash
export SETU_LLM_API_KEY=...            # your key
export SETU_LLM_ALLOW_HOSTED=1 SETU_LLM_REASONING=none SETU_LLM_RETRIES=3
SKIP_SEED=1 scripts/run_demo.sh
```

Without them every agent uses its approved/bank fallback. Each Raju turn's last card says which ("मॉडल ने लिखा, जाँच
में पास हुआ" or "मंज़ूर वाक्य-भंडार से").

## The learning experience

- **आज सीखें (home):** one recommended lesson, chosen from the learner's real state (due reviews first, then a rule
  Raju forgot, then the next unlocked activity in ladder order, then Raju practice, then conversations), with the reason,
  the estimated minutes and one "पाठ शुरू करें" button. A small bar shows overall progress and the current stage.
- **Lesson screens:** one exercise per screen, a progress bar and an exit (×), nothing else. Each new item: intro card
  (example + Hindi twin/meaning) → guided step (pick) → independent step (write on the Telugu keyboard or type) →
  immediate feedback.
- **Raju (राजू · आपका सहपाठी):** writes a sentence with one planted Hindi-habit error; the learner corrects it or says
  it is right. **दीदी (coach)** appears after a first miss with a hint that never holds the answer; after a second
  miss she shows the answer to copy. **रवि (Telugu friend)** speaks approved lines in conversations.
- **मेरी प्रगति:** the ladder (can do · learning · later). **समीक्षा:** goes straight to whatever is due.
  **बातचीत:** the conversation scenes.

## Steps

| Step | Where | What to show |
|---|---|---|
| Home | `/` | one lesson, its reason and time |
| Lesson | "पाठ शुरू करें" | intro → pick → write → feedback |
| Raju + coach | `/learn/rules` | write the Telugu for the Hindi meaning; once Raju appears, submit his sentence unchanged → दीदी's hint; then correct it → the card shows the verdict and Raju's new state |
| Conversation | pass `/learn/placement` first, then `/learn/scenes` | रवि's line → what did he mean → your reply |
| Progress | `/ladder` | |
| Teacher | teacher login → `/teacher` | review, the unsure queue |

Screenshots (desktop and mobile) are in `docs/submission/screenshots/` (`python -m scripts.screenshots <handle>
<passphrase>` re-captures them).
