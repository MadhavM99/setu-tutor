# Demo guide

```bash
cd ~/Developer/setu-tutor
scripts/run_demo.sh            # starts Postgres (Docker), rebuilds the isolated setu_demo DB, serves http://127.0.0.1:8000
# prints the learner and teacher logins (passphrase: डेमो पासवर्ड बारह); SKIP_SEED=1 keeps the existing demo DB
```

Optional real model (self-hosted): in another terminal `~/.lmstudio/bin/lms server start && ~/.lmstudio/bin/lms load
qwen/qwen3.5-9b`, then start the demo with `SETU_LLM_URL=http://localhost:1234/v1 SETU_LLM_MODEL=qwen/qwen3.5-9b
scripts/run_demo.sh`. Without it every agent uses its approved/bank fallback (the page says which).

Open **http://127.0.0.1:8000** → अंदर आएँ → the printed learner handle + passphrase. Every page shows the demo banner.

| Step | Where | What to show |
|---|---|---|
| Dashboard | `/` | links to every activity |
| Letters, aksharas | `/learn/letters`, `/learn/aksharas` | twin intro → choice (recognition) → cue-free recall on the Telugu keyboard; aksharas unlock after their letters |
| Words, chunks | `/learn/words`, `/learn/chunks` | cognates, false-friend trap, built recall; chunks inside scenes |
| Placement | `/learn/placement` | adaptive test from L2; "बस, यहीं से शुरू करें" |
| Ladder | `/ladder` | can do · learning (placed: पक्का करना बाकी) · later, one explained next step |
| **Raju** | `/learn/rules` | new rule card → own sentence (type the Telugu for the Hindi meaning, e.g. तुम आ रहे हो क्या → నువ్వు వస్తావా) → Raju appears (demo threshold 1 rule) with a planted error → type the planted sentence unchanged to see the **coach hint**, then the correction; the last card shows **इस बार क्या हुआ**: Raju's sentence (model or bank), your answer, the checker's verdict, Raju's new state |
| **Native friend** | `/learn/scenes` | opens after the scene's chunks are mastered or placed (fastest: pass placement) → comprehension → own reply; an unexpected reply gives the Hindi fallback |
| Teacher | log in with the teacher handle → `/teacher` | content review, the unsure queue (settle an answer), rule review |

Mobile: the pages are single-column HTML; check at a narrow browser width. No screenshots were captured (no
screenshot tool is installed in the environment).
