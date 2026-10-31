# Challenges and mitigation

| Challenge | Where it shows now | Mitigation (concrete) |
|---|---|---|
| Telugu content validation | All 25 rules have open validation issues; most lack a Hindi explanation; every Telugu line is unreviewed | Fix rule content in `content/` (explanations, answer-revealing titles DQ-08), re-import as drafts; review in the console (F0/F1 built) |
| Native-speaker availability | 0 native approvals; nothing visible to real learners | Recruit 2 native Telugu reviewers + 1 tie-breaker; batch review in `/teacher/review`; κ page (F2) to monitor agreement |
| Model hosting / GPU | No endpoint was running; a 9B model (qwen3.5-9b, LM Studio) exists on a 16 GB M1 Pro laptop | Run the baselines on that laptop first (`lms server start`); request a GPU host for Gemma 3 12B (P-MODEL-01) |
| Hallucinated Telugu | Possible in any model output | Model text reaches learners only if it is an approved form (friend) or passes the leak filter (Raju); else the bank; all logged |
| Answer leakage | Hints and sentences | `check_hint_has_no_answer` (Telugu, Devanagari, Latin forms); planted turns accept only the approved planted sentence; tested |
| Checker uncertainty | M-09 unsure rate 0.182 > 0.15 | Teacher queue settles unsure answers (built); teacher labels decide whether to adopt "incomplete → wrong"; threshold not relaxed |
| Simulator limitations | Effects are assumptions; A < C on recall; floor at day 7 | Calibrate on pilot data; keep `no_mechanism_bonus` and sensitivity runs in every report; never report simulation as human evidence |
| Application integration | Long path before Raju appears (3 ready rules) | Demo-only `SETU_CLASSMATE_START_MIN_RULES` (recorded in the session config); proper session composer is remaining work |
| Production practice (R-17) | Simulation: C's 21 full productions beat A's 6 own + cued fixes | Experiment with more own sentences per session in A; test in the pilot |
