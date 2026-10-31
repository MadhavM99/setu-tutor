# Experiment results (mid-submission, 31 Oct 2026)

> **Every number here comes from a parametric software simulation (`sim-0.1`) of simulated learners, not from
> people.** It shows what follows from the stated assumptions (see `experiment_design.md`); it is not evidence that
> reverse learning helps human learners.

Source: `reports/simulation/results.json` (reproduce: `python -m setu.research.simulator`, about 1 s).
n = 100 simulated learners per condition (20 matched profiles × 5 seeds). Recall/transfer/detection are
probabilities (0–1). Day-7 values: mean ± SD. Δ rows: paired difference, 95% CI, Cohen's d_z.

| Run | Cond. | Recall d0 | d1 | d2 | d7 | Transfer d7 | Detection d7 | Hints | Wrong fixes | False alarms | Own sentences | Time (s) | Model calls (expected) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| main | A | 0.267 | 0.325 | 0.394 | 0.046 ± 0.024 | 0.028 | 0.245 | 17.7 | 13.4 | 0.03 | 6.0 | 920 | 28.4 |
| main | B | 0.248 | 0.290 | 0.352 | 0.019 ± 0.011 | 0.010 | 0.177 | 4.5 | 0.0 | 0.00 | 6.0 | 765 | 0.0 |
| main | C | 0.270 | 0.327 | 0.404 | 0.051 ± 0.025 | 0.027 | 0.183 | 16.0 | 0.0 | 0.00 | 21.0 | 840 | 0.0 |
| main | Δ A-B | | | | +0.027 [+0.023, +0.032] dz 1.231 | +0.019 | +0.068 | | | | | | |
| main | Δ A-C | | | | -0.005 [-0.009, -0.001] dz -0.246 | +0.001 | +0.062 | | | | | | |
| main | Δ B-C | | | | -0.032 [-0.036, -0.028] dz -1.47 | -0.018 | -0.005 | | | | | | |
| no_mechanism_bonus | A | 0.267 | 0.325 | 0.393 | 0.044 ± 0.023 | 0.027 | 0.182 | 18.0 | 13.8 | 0.03 | 6.0 | 919 | 28.8 |
| no_mechanism_bonus | B | 0.248 | 0.290 | 0.352 | 0.019 ± 0.011 | 0.010 | 0.177 | 4.5 | 0.0 | 0.00 | 6.0 | 765 | 0.0 |
| no_mechanism_bonus | C | 0.270 | 0.327 | 0.404 | 0.051 ± 0.025 | 0.027 | 0.183 | 16.0 | 0.0 | 0.00 | 21.0 | 840 | 0.0 |
| no_mechanism_bonus | Δ A-B | | | | +0.025 [+0.021, +0.029] dz 1.166 | +0.018 | +0.005 | | | | | | |
| no_mechanism_bonus | Δ A-C | | | | -0.007 [-0.011, -0.003] dz -0.318 | +0.000 | -0.001 | | | | | | |
| no_mechanism_bonus | Δ B-C | | | | -0.032 [-0.036, -0.028] dz -1.47 | -0.018 | -0.005 | | | | | | |
| raju_forgetting_off | A | 0.267 | 0.314 | 0.376 | 0.038 ± 0.022 | 0.021 | 0.241 | 17.3 | 13.0 | 0.15 | 6.0 | 903 | 28.0 |
| raju_forgetting_off | B | 0.248 | 0.290 | 0.352 | 0.019 ± 0.011 | 0.010 | 0.177 | 4.5 | 0.0 | 0.00 | 6.0 | 765 | 0.0 |
| raju_forgetting_off | C | 0.270 | 0.327 | 0.404 | 0.051 ± 0.025 | 0.027 | 0.183 | 16.0 | 0.0 | 0.00 | 21.0 | 840 | 0.0 |
| raju_forgetting_off | Δ A-B | | | | +0.019 [+0.015, +0.022] dz 0.954 | +0.011 | +0.063 | | | | | | |
| raju_forgetting_off | Δ A-C | | | | -0.014 [-0.018, -0.009] dz -0.638 | -0.006 | +0.058 | | | | | | |
| raju_forgetting_off | Δ B-C | | | | -0.032 [-0.036, -0.028] dz -1.47 | -0.018 | -0.005 | | | | | | |
| direct_answers | A | 0.244 | 0.285 | 0.342 | 0.021 ± 0.015 | 0.012 | 0.239 | 18.1 | 13.6 | 0.02 | 6.0 | 920 | 28.6 |
| direct_answers | B | 0.241 | 0.280 | 0.339 | 0.015 ± 0.009 | 0.007 | 0.177 | 4.4 | 0.0 | 0.00 | 6.0 | 765 | 0.0 |
| direct_answers | C | 0.249 | 0.290 | 0.356 | 0.028 ± 0.021 | 0.013 | 0.179 | 16.3 | 0.0 | 0.00 | 21.0 | 840 | 0.0 |
| direct_answers | Δ A-B | | | | +0.007 [+0.004, +0.009] dz 0.527 | +0.005 | +0.062 | | | | | | |
| direct_answers | Δ A-C | | | | -0.006 [-0.010, -0.003] dz -0.328 | -0.001 | +0.060 | | | | | | |
| direct_answers | Δ B-C | | | | -0.013 [-0.017, -0.010] dz -0.746 | -0.006 | -0.002 | | | | | | |
| no_error_share_0 | A | 0.267 | 0.325 | 0.396 | 0.046 ± 0.025 | 0.029 | 0.245 | 17.8 | 13.5 | 0.00 | 6.0 | 921 | 28.5 |
| no_error_share_0 | B | 0.248 | 0.290 | 0.352 | 0.019 ± 0.011 | 0.010 | 0.177 | 4.5 | 0.0 | 0.00 | 6.0 | 765 | 0.0 |
| no_error_share_0 | C | 0.270 | 0.327 | 0.404 | 0.051 ± 0.025 | 0.027 | 0.183 | 16.0 | 0.0 | 0.00 | 21.0 | 840 | 0.0 |
| no_error_share_0 | Δ A-B | | | | +0.027 [+0.023, +0.032] dz 1.229 | +0.019 | +0.068 | | | | | | |
| no_error_share_0 | Δ A-C | | | | -0.005 [-0.009, -0.001] dz -0.226 | +0.002 | +0.063 | | | | | | |
| no_error_share_0 | Δ B-C | | | | -0.032 [-0.036, -0.028] dz -1.47 | -0.018 | -0.005 | | | | | | |
| no_error_share_0.4 | A | 0.267 | 0.325 | 0.394 | 0.046 ± 0.024 | 0.029 | 0.245 | 17.7 | 13.4 | 0.03 | 6.0 | 919 | 28.4 |
| no_error_share_0.4 | B | 0.248 | 0.290 | 0.352 | 0.019 ± 0.011 | 0.010 | 0.177 | 4.5 | 0.0 | 0.00 | 6.0 | 765 | 0.0 |
| no_error_share_0.4 | C | 0.270 | 0.327 | 0.404 | 0.051 ± 0.025 | 0.027 | 0.183 | 16.0 | 0.0 | 0.00 | 21.0 | 840 | 0.0 |
| no_error_share_0.4 | Δ A-B | | | | +0.027 [+0.023, +0.032] dz 1.241 | +0.019 | +0.067 | | | | | | |
| no_error_share_0.4 | Δ A-C | | | | -0.005 [-0.009, -0.001] dz -0.239 | +0.002 | +0.062 | | | | | | |
| no_error_share_0.4 | Δ B-C | | | | -0.032 [-0.036, -0.028] dz -1.47 | -0.018 | -0.005 | | | | | | |
| own_sentences_0 | A | 0.237 | 0.258 | 0.310 | 0.030 ± 0.022 | 0.017 | 0.242 | 13.6 | 13.6 | 0.00 | 0.0 | 680 | 28.6 |
| own_sentences_0 | B | 0.218 | 0.222 | 0.259 | 0.005 ± 0.004 | 0.002 | 0.175 | 0.0 | 0.0 | 0.00 | 0.0 | 525 | 0.0 |
| own_sentences_0 | C | 0.241 | 0.260 | 0.314 | 0.026 ± 0.021 | 0.010 | 0.179 | 12.2 | 0.0 | 0.00 | 15.0 | 600 | 0.0 |
| own_sentences_0 | Δ A-B | | | | +0.025 [+0.021, +0.029] dz 1.188 | +0.015 | +0.067 | | | | | | |
| own_sentences_0 | Δ A-C | | | | +0.004 [-0.000, +0.008] dz 0.19 | +0.007 | +0.063 | | | | | | |
| own_sentences_0 | Δ B-C | | | | -0.021 [-0.025, -0.017] dz -1.111 | -0.009 | -0.004 | | | | | | |
| sensitivity_half_life_4 | A | 0.267 | 0.343 | 0.418 | 0.195 ± 0.036 | 0.132 | 0.280 | 17.3 | 13.2 | 0.05 | 6.0 | 919 | 28.2 |
| sensitivity_half_life_4 | B | 0.248 | 0.309 | 0.375 | 0.140 ± 0.029 | 0.088 | 0.198 | 4.4 | 0.0 | 0.00 | 6.0 | 765 | 0.0 |
| sensitivity_half_life_4 | C | 0.270 | 0.349 | 0.431 | 0.210 ± 0.044 | 0.138 | 0.210 | 15.2 | 0.0 | 0.00 | 21.0 | 840 | 0.0 |
| sensitivity_half_life_4 | Δ A-B | | | | +0.054 [+0.050, +0.059] dz 2.422 | +0.044 | +0.082 | | | | | | |
| sensitivity_half_life_4 | Δ A-C | | | | -0.016 [-0.021, -0.011] dz -0.597 | -0.006 | +0.070 | | | | | | |
| sensitivity_half_life_4 | Δ B-C | | | | -0.070 [-0.076, -0.065] dz -2.507 | -0.050 | -0.012 | | | | | | |
## Reading the results

1. **A vs B (the contribution of reverse learning, other things matched):** A is higher on day-7 recall
   (+0.027, 95% CI [+0.023, +0.032]; with a 4-day half-life +0.054 [+0.050, +0.059]), transfer and detection.
   With the two assumed A-only effects switched off (`no_mechanism_bonus`) the recall and transfer advantage stays
   (+0.025) but the **detection advantage disappears** (+0.068 → +0.005). So in this model A beats B mainly because
   correcting Raju is *cued production* while B is *restudy* — a difference in retrieval demand, not something
   special about teaching a classmate.
2. **A vs C (full SETU vs a conventional tutor):** A is slightly **lower** on day-7 recall (−0.005 [−0.009,
   −0.001]; −0.016 with a 4-day half-life) and about equal on transfer; higher on detection only while the assumed
   noticing effect is on. C gives 21 full-retrieval productions per learner against A's 6 own sentences plus cued
   corrections. This repeats the newer paper's v0 finding (A > B, A < C) and is the main risk (R-17).
3. **B vs C:** B is lowest on everything; restudy without retrieval does worst.
4. **Ablations:** removing own sentences hurts every condition and is where A comes closest to C (A−C +0.004,
   CI touches 0): own-sentence production matters. Direct answers instead of hints lower recall in all conditions.
   Raju forgetting off lowers A's day-7 recall (0.046 → 0.038). No-error share 0–0.4 changes recall by < 0.001 in
   this model (no-error turns only affect false alarms here), so the simulator cannot inform that choice yet.
5. **Floor effect:** with the default 1.5-day half-life, day-7 recall is near 0.05 in all conditions; the
   sensitivity run (4 days, all conditions) keeps the same ordering.
6. **Time on task is not equal** (A 920 s, C 840 s, B 765 s in assumed seconds): the conditions are matched on the
   number of exchanges, not on time.

## Model-generation baselines

`reports/generation_baselines.json`: **status `not_run`** — no self-hosted endpoint was running during the sprint
(LM Studio with `qwen/qwen3.5-9b` is installed on the development machine but its server was not started). No
model numbers are reported. Command to run them is in `experiment_design.md` §3.

## Deterministic module results (from Phase 2, held-out Stage-A split)

M-05 1.00, M-07 1.00, M-08 0.00, M-14 0, M-54 0 pass; **M-09 unsure rate 0.182 fails** (target 0.15); 13 gate metrics
not measured. Team-generated cases: optimistic. (`reports/scorecard-2026-10-31-heldout.md`)
