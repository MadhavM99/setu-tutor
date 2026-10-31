# Experiment results (mid-submission; updated 31 Oct 2026)

Sections: **A.** original simulation `sim-0.1` (unchanged) · **B.** validity review · **C.** improved simulation
`sim-0.2` · **D.** real-model measurements · **E.** rejected or exploratory runs.

## A. Original simulation (`sim-0.1`, 31 Oct 2026) — kept as the baseline

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

## (sim-0.1) Model-generation baselines — superseded by section D

`reports/generation_baselines.json`: **status `not_run`** — no self-hosted endpoint was running during the sprint
(LM Studio with `qwen/qwen3.5-9b` is installed on the development machine but its server was not started). No
model numbers are reported. Command to run them is in `experiment_design.md` §3.

## Deterministic module results (from Phase 2, held-out Stage-A split)

M-05 1.00, M-07 1.00, M-08 0.00, M-14 0, M-54 0 pass; **M-09 unsure rate 0.182 fails** (target 0.15); 13 gate metrics
not measured. Team-generated cases: optimistic. (`reports/scorecard-2026-10-31-heldout.md`)


## B. Validity review of `sim-0.1`

| Question | Finding |
|---|---|
| Why does recall approach zero by day 7? | The memory model was an ad-hoc exponential half-life of 1.5 days that only grew after a later-day success; day 7 is five days after the last practice, so recall ≈ k·2^(−5/h) ≈ 0.05. Too aggressive and not based on anything external. |
| Are the learning-transition probabilities independently justified? | No. They encode qualitative findings (retrieval practice > restudy; cues weaken retrieval) but the magnitudes are assumptions. |
| Does the model reward reverse learning by construction? | Partly: two A-only effects (self-explanation, noticing practice) were on by default. Switching them off removed A's detection advantage. |
| Equivalent exposure and practice? | Same rules, sequence and number of exchanges; the kind of practice differs by design (that is the treatment). |
| Time on task matched? | **No** (A 920 s, C 840 s, B 765 s of assumed seconds). |

## C. Improved simulation (`sim-0.2`)

Code `setu/research/simulator_v2.py`; results `reports/simulation_v2/results.json`; n = 100 simulated learners per
condition (the same 20 matched profiles × 5 seeds as `sim-0.1`). Changes: memory = the project's own FSRS scheduler
(py-fsrs default parameters) with the app's rating rules (cue-free correct = Good, correct with a visible cue or
answer = Hard, wrong = Again); A-only effects **off** in the main runs; two designs — matched exchanges and matched
time (300 s per session); a vocabulary card per rule; sensitivity runs. Parameters were fixed before the run and not
changed after seeing results (one modelling bug was corrected, see E).

| Run | Cond. | Recall d0 | d1 | d2 | d7 (mean ± SD) | Production d7 | Transfer d7 | Detection d7 | Vocabulary d7 | Hints | Wrong fixes | Exchanges | Time (s) | Model calls (expected) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| main_matched_exchanges | A | 0.333 | 0.387 | 0.431 | 0.253 ± 0.037 | 0.239 | 0.192 | 0.218 | 0.512 | 16.3 | 12.7 | 21.0 | 909 | 27.7 |
| main_matched_exchanges | B | 0.315 | 0.366 | 0.416 | 0.329 ± 0.042 | 0.313 | 0.252 | 0.231 | 0.743 | 3.8 | 0.0 | 21.0 | 765 | 0.0 |
| main_matched_exchanges | C | 0.338 | 0.403 | 0.462 | 0.306 ± 0.051 | 0.286 | 0.226 | 0.226 | 0.593 | 13.2 | 0.0 | 21.0 | 840 | 0.0 |
| main_matched_exchanges | Δ A-B | +0.018 | | | -0.076 [-0.081, -0.071] d_z -2.825 | -0.073 | -0.060 | -0.012 | -0.231 | | | | | |
| main_matched_exchanges | Δ A-C | -0.005 | | | -0.053 [-0.060, -0.047] d_z -1.622 | -0.046 | -0.034 | -0.008 | -0.081 | | | | | |
| main_matched_exchanges | Δ B-C | -0.023 | | | +0.023 [+0.017, +0.029] d_z 0.74 | +0.027 | +0.027 | +0.004 | +0.150 | | | | | |
| main_matched_time | A | 0.321 | 0.365 | 0.404 | 0.243 ± 0.037 | 0.230 | 0.184 | 0.217 | 0.514 | 15.1 | 12.9 | 18.4 | 806 | 28.0 |
| main_matched_time | B | 0.322 | 0.380 | 0.436 | 0.344 ± 0.041 | 0.329 | 0.267 | 0.233 | 0.751 | 3.8 | 0.0 | 24.0 | 870 | 0.0 |
| main_matched_time | C | 0.338 | 0.403 | 0.462 | 0.306 ± 0.051 | 0.286 | 0.226 | 0.226 | 0.593 | 13.2 | 0.0 | 21.0 | 840 | 0.0 |
| main_matched_time | Δ A-B | -0.001 | | | -0.101 [-0.105, -0.096] d_z -4.06 | -0.100 | -0.084 | -0.017 | -0.237 | | | | | |
| main_matched_time | Δ A-C | -0.017 | | | -0.063 [-0.069, -0.057] d_z -2.086 | -0.056 | -0.042 | -0.009 | -0.079 | | | | | |
| main_matched_time | Δ B-C | -0.016 | | | +0.038 [+0.032, +0.044] d_z 1.22 | +0.043 | +0.042 | +0.007 | +0.158 | | | | | |
| hypothesis_a_only_effects | A | 0.333 | 0.386 | 0.433 | 0.258 ± 0.039 | 0.244 | 0.196 | 0.290 | 0.520 | 15.6 | 12.0 | 21.0 | 909 | 27.0 |
| hypothesis_a_only_effects | B | 0.315 | 0.366 | 0.416 | 0.329 ± 0.042 | 0.313 | 0.252 | 0.231 | 0.743 | 3.8 | 0.0 | 21.0 | 765 | 0.0 |
| hypothesis_a_only_effects | C | 0.338 | 0.403 | 0.462 | 0.306 ± 0.051 | 0.286 | 0.226 | 0.226 | 0.593 | 13.2 | 0.0 | 21.0 | 840 | 0.0 |
| hypothesis_a_only_effects | Δ A-B | +0.018 | | | -0.071 [-0.077, -0.065] d_z -2.328 | -0.069 | -0.057 | +0.059 | -0.223 | | | | | |
| hypothesis_a_only_effects | Δ A-C | -0.005 | | | -0.048 [-0.055, -0.042] d_z -1.43 | -0.042 | -0.030 | +0.064 | -0.073 | | | | | |
| hypothesis_a_only_effects | Δ B-C | -0.023 | | | +0.023 [+0.017, +0.029] d_z 0.74 | +0.027 | +0.027 | +0.004 | +0.150 | | | | | |
| no_testing_effect | A | 0.305 | 0.337 | 0.367 | 0.212 ± 0.035 | 0.201 | 0.161 | 0.211 | 0.506 | 17.0 | 13.0 | 21.0 | 909 | 28.0 |
| no_testing_effect | B | 0.305 | 0.347 | 0.388 | 0.307 ± 0.042 | 0.292 | 0.236 | 0.227 | 0.742 | 3.9 | 0.0 | 21.0 | 765 | 0.0 |
| no_testing_effect | C | 0.303 | 0.339 | 0.373 | 0.243 ± 0.044 | 0.227 | 0.179 | 0.215 | 0.578 | 14.1 | 0.0 | 21.0 | 840 | 0.0 |
| no_testing_effect | Δ A-B | -0.000 | | | -0.096 [-0.100, -0.091] d_z -4.381 | -0.092 | -0.075 | -0.016 | -0.235 | | | | | |
| no_testing_effect | Δ A-C | +0.001 | | | -0.031 [-0.035, -0.026] d_z -1.285 | -0.026 | -0.018 | -0.004 | -0.072 | | | | | |
| no_testing_effect | Δ B-C | +0.002 | | | +0.065 [+0.061, +0.069] d_z 3.224 | +0.066 | +0.057 | +0.011 | +0.164 | | | | | |
| raju_forgetting_off | A | 0.333 | 0.382 | 0.424 | 0.254 ± 0.038 | 0.240 | 0.192 | 0.219 | 0.528 | 15.9 | 12.3 | 21.0 | 896 | 27.3 |
| raju_forgetting_off | B | 0.315 | 0.366 | 0.416 | 0.329 ± 0.042 | 0.313 | 0.252 | 0.231 | 0.743 | 3.8 | 0.0 | 21.0 | 765 | 0.0 |
| raju_forgetting_off | C | 0.338 | 0.403 | 0.462 | 0.306 ± 0.051 | 0.286 | 0.226 | 0.226 | 0.593 | 13.2 | 0.0 | 21.0 | 840 | 0.0 |
| raju_forgetting_off | Δ A-B | +0.018 | | | -0.075 [-0.081, -0.070] d_z -2.544 | -0.073 | -0.060 | -0.012 | -0.215 | | | | | |
| raju_forgetting_off | Δ A-C | -0.005 | | | -0.052 [-0.059, -0.046] d_z -1.54 | -0.046 | -0.034 | -0.008 | -0.065 | | | | | |
| raju_forgetting_off | Δ B-C | -0.023 | | | +0.023 [+0.017, +0.029] d_z 0.74 | +0.027 | +0.027 | +0.004 | +0.150 | | | | | |
| direct_answers | A | 0.313 | 0.353 | 0.387 | 0.227 ± 0.039 | 0.214 | 0.172 | 0.214 | 0.506 | 16.8 | 12.9 | 21.0 | 907 | 27.9 |
| direct_answers | B | 0.310 | 0.357 | 0.405 | 0.321 ± 0.044 | 0.305 | 0.246 | 0.229 | 0.743 | 3.9 | 0.0 | 21.0 | 765 | 0.0 |
| direct_answers | C | 0.321 | 0.374 | 0.425 | 0.282 ± 0.054 | 0.263 | 0.207 | 0.222 | 0.585 | 13.7 | 0.0 | 21.0 | 840 | 0.0 |
| direct_answers | Δ A-B | +0.004 | | | -0.095 [-0.100, -0.089] d_z -3.323 | -0.091 | -0.074 | -0.015 | -0.237 | | | | | |
| direct_answers | Δ A-C | -0.008 | | | -0.055 [-0.062, -0.048] d_z -1.507 | -0.049 | -0.036 | -0.008 | -0.079 | | | | | |
| direct_answers | Δ B-C | -0.011 | | | +0.039 [+0.033, +0.046] d_z 1.209 | +0.043 | +0.039 | +0.007 | +0.158 | | | | | |
| no_error_share_0 | A | 0.333 | 0.389 | 0.440 | 0.254 ± 0.038 | 0.241 | 0.194 | 0.219 | 0.510 | 16.9 | 13.3 | 21.0 | 923 | 28.3 |
| no_error_share_0 | B | 0.315 | 0.366 | 0.416 | 0.329 ± 0.042 | 0.313 | 0.252 | 0.231 | 0.743 | 3.8 | 0.0 | 21.0 | 765 | 0.0 |
| no_error_share_0 | C | 0.338 | 0.403 | 0.462 | 0.306 ± 0.051 | 0.286 | 0.226 | 0.226 | 0.593 | 13.2 | 0.0 | 21.0 | 840 | 0.0 |
| no_error_share_0 | Δ A-B | +0.018 | | | -0.075 [-0.080, -0.069] d_z -2.736 | -0.072 | -0.059 | -0.012 | -0.233 | | | | | |
| no_error_share_0 | Δ A-C | -0.005 | | | -0.052 [-0.059, -0.045] d_z -1.545 | -0.045 | -0.032 | -0.008 | -0.083 | | | | | |
| no_error_share_0 | Δ B-C | -0.023 | | | +0.023 [+0.017, +0.029] d_z 0.74 | +0.027 | +0.027 | +0.004 | +0.150 | | | | | |
| no_error_share_0.4 | A | 0.333 | 0.384 | 0.425 | 0.252 ± 0.037 | 0.238 | 0.191 | 0.218 | 0.515 | 16.0 | 12.4 | 21.0 | 899 | 27.4 |
| no_error_share_0.4 | B | 0.315 | 0.366 | 0.416 | 0.329 ± 0.042 | 0.313 | 0.252 | 0.231 | 0.743 | 3.8 | 0.0 | 21.0 | 765 | 0.0 |
| no_error_share_0.4 | C | 0.338 | 0.403 | 0.462 | 0.306 ± 0.051 | 0.286 | 0.226 | 0.226 | 0.593 | 13.2 | 0.0 | 21.0 | 840 | 0.0 |
| no_error_share_0.4 | Δ A-B | +0.018 | | | -0.077 [-0.083, -0.072] d_z -2.846 | -0.075 | -0.062 | -0.013 | -0.229 | | | | | |
| no_error_share_0.4 | Δ A-C | -0.005 | | | -0.055 [-0.061, -0.048] d_z -1.578 | -0.048 | -0.035 | -0.008 | -0.078 | | | | | |
| no_error_share_0.4 | Δ B-C | -0.023 | | | +0.023 [+0.017, +0.029] d_z 0.74 | +0.027 | +0.027 | +0.004 | +0.150 | | | | | |
| own_sentences_0 | A | 0.308 | 0.338 | 0.364 | 0.227 ± 0.034 | 0.214 | 0.170 | 0.214 | 0.507 | 13.0 | 13.0 | 15.0 | 672 | 28.0 |
| own_sentences_0 | B | 0.291 | 0.321 | 0.352 | 0.305 ± 0.043 | 0.288 | 0.230 | 0.227 | 0.782 | 0.0 | 0.0 | 15.0 | 525 | 0.0 |
| own_sentences_0 | C | 0.314 | 0.358 | 0.398 | 0.280 ± 0.046 | 0.260 | 0.203 | 0.222 | 0.592 | 9.9 | 0.0 | 15.0 | 600 | 0.0 |
| own_sentences_0 | Δ A-B | +0.017 | | | -0.077 [-0.081, -0.074] d_z -4.095 | -0.074 | -0.060 | -0.013 | -0.275 | | | | | |
| own_sentences_0 | Δ A-C | -0.006 | | | -0.053 [-0.058, -0.048] d_z -1.92 | -0.046 | -0.033 | -0.008 | -0.085 | | | | | |
| own_sentences_0 | Δ B-C | -0.024 | | | +0.024 [+0.019, +0.030] d_z 0.884 | +0.028 | +0.027 | +0.004 | +0.190 | | | | | |
| memory_stability_x0.5 | A | 0.333 | 0.382 | 0.424 | 0.228 ± 0.034 | 0.215 | 0.173 | 0.214 | 0.459 | 16.4 | 12.8 | 21.0 | 908 | 27.8 |
| memory_stability_x0.5 | B | 0.315 | 0.362 | 0.410 | 0.302 ± 0.039 | 0.287 | 0.232 | 0.226 | 0.681 | 3.8 | 0.0 | 21.0 | 765 | 0.0 |
| memory_stability_x0.5 | C | 0.338 | 0.399 | 0.456 | 0.279 ± 0.048 | 0.260 | 0.205 | 0.222 | 0.537 | 13.2 | 0.0 | 21.0 | 840 | 0.0 |
| memory_stability_x0.5 | Δ A-B | +0.018 | | | -0.074 [-0.080, -0.069] d_z -2.876 | -0.072 | -0.059 | -0.012 | -0.222 | | | | | |
| memory_stability_x0.5 | Δ A-C | -0.005 | | | -0.051 [-0.058, -0.044] d_z -1.541 | -0.045 | -0.032 | -0.007 | -0.078 | | | | | |
| memory_stability_x0.5 | Δ B-C | -0.023 | | | +0.024 [+0.018, +0.029] d_z 0.789 | +0.027 | +0.026 | +0.004 | +0.144 | | | | | |
| memory_stability_x2 | A | 0.333 | 0.391 | 0.439 | 0.279 ± 0.040 | 0.264 | 0.212 | 0.223 | 0.569 | 16.3 | 12.7 | 21.0 | 909 | 27.7 |
| memory_stability_x2 | B | 0.315 | 0.368 | 0.420 | 0.354 ± 0.044 | 0.337 | 0.272 | 0.235 | 0.801 | 3.8 | 0.0 | 21.0 | 765 | 0.0 |
| memory_stability_x2 | C | 0.338 | 0.407 | 0.468 | 0.335 ± 0.053 | 0.313 | 0.247 | 0.231 | 0.652 | 13.1 | 0.0 | 21.0 | 840 | 0.0 |
| memory_stability_x2 | Δ A-B | +0.018 | | | -0.075 [-0.081, -0.070] d_z -2.715 | -0.073 | -0.060 | -0.012 | -0.233 | | | | | |
| memory_stability_x2 | Δ A-C | -0.005 | | | -0.056 [-0.063, -0.050] d_z -1.635 | -0.049 | -0.035 | -0.008 | -0.083 | | | | | |
| memory_stability_x2 | Δ B-C | -0.023 | | | +0.019 [+0.013, +0.025] d_z 0.606 | +0.024 | +0.025 | +0.004 | +0.149 | | | | | |

### What `sim-0.2` shows (simulation only)

1. **The result reverses `sim-0.1`.** Under FSRS memory with the app's rating rules, A (reverse learning) has the
   **lowest** day-7 recall: A−B −0.076 [−0.081, −0.071], A−C −0.053 [−0.060, −0.047] with matched exchanges; −0.101
   and −0.063 with matched time. Production and transfer follow the same order.
2. **Why, mechanically:** a correction made with the rest of Raju's sentence visible is a *cued* answer (rated Hard),
   and a missed planted error is a failed retrieval (rated Again: a lapse that resets stability). B (study the error
   and its correction, then type it while visible) never lapses; C retrieves cue-free (Good) more often. FSRS turns
   these rating differences into large stability differences by day 7.
3. **The direction holds across every sensitivity run** (memory stability ×0.5 / ×2, no testing effect, forgetting off,
   direct answers, no-error share 0 / 0.4, own sentences 0). The A-only hypothesis (self-explanation + noticing) adds
   detection (+0.06) but not enough recall to change the order.
4. **B ≥ C here, which contradicts the testing-effect literature** this model was meant to encode. Treating restudy as
   a Hard FSRS review with no possibility of failure is probably too generous to B; the simulator cannot settle this.

### What the two simulations together demonstrate

They do **not** show that reverse learning helps or hurts people. They show that the conclusion depends on the memory
model (`sim-0.1` ad-hoc: A > B, A ≈ C; `sim-0.2` FSRS: A < C < B) and on how corrections of a visible sentence are
counted. The single robust pattern across both: **A is not better than C on recall**, and cue-free own sentences matter.
The design questions that would decide it — whether correcting a planted error is retrieval or recognition, and how
much missed errors cost — need the human pilot (Phase 6), not more simulation.

## D. Real-model measurements (hosted `gemini-3.5-flash`, 31 Oct 2026)

**Real inference works**, but **the 29-case baseline comparison is not yet valid**: the free-tier quota of the key
ran out during the run ("You exceeded your current quota, please check your plan and billing details"), so most calls
returned HTTP 429 instead of a model reply.

### D1. Individual real calls (verified)

| Call | Result |
|---|---|
| Smoke test (direct client) | 200 OK, `gemini-3.5-flash`, 2.6 s with `reasoning_effort=none` (without it, reasoning tokens truncated the JSON) |
| `gemini-3.8-flash` (the requested model) | 503 "This model is currently experiencing high demand" (3 attempts) |
| `gemini-3.7-flash` | 429 |
| Raju in the live app | 200 OK, 13.7 s, 146 prompt + 14 completion tokens; proposed `నేను నహీ వెళ్తాను`; passed the leak filter; shown to the learner (`model_call` row in `setu_demo`) |
| Coach in the live app (first run) | 200 OK; the hint leaked no answer but mixed in Telugu words the learner had not met → **new rule: model hints may contain no Telugu** (`TELUGU_IN_HINT`) |
| Coach and friend in the live app (second run) | 429 → the generic hint and the approved line were shown (fallback worked) |
| Outage test (invalid key) | 400 → Raju used the bank sentence, the coach the generic hint, the friend the approved line |

### D2. Baseline run 1 (rate-limited; kept as `reports/generation_baselines_run1_rate_limited.json`)

| Method | Cases | What happened |
|---|---|---|
| tool-assisted | 29 | partly answered: 5/29 passed the filter (all 5 exactly the planned error; 2 cases had an answer-leaking draft rejected); the rest mixes model rejections with 429s, which run 1 did not separate |
| blind resampling | 29 | no model reply (0 tokens): rate-limited |
| prompt-only | 29 | no model reply: rate-limited |
| coach (29) / friend (12 + 12 injection) | — | no model reply: rate-limited; the learner saw only approved text in every friend case |

These are **not** quality measurements and are not used to compare the methods. The harness now records every
call's error, counts a case only if the model replied (`evaluable`), and throttles to one call every 6 s
(`SETU_EVAL_INTERVAL`). To produce the real comparison after the quota resets (or with billing enabled):
`source <your env file> && python -m setu.research.generation_baselines` (~260 calls, about 30 minutes).

## E. Rejected and exploratory runs (kept for transparency)

| File | What it was | Why rejected |
|---|---|---|
| `reports/simulation_v2/first_run_same_semantics.json` | first `sim-0.2` run | identical to the final run (kept to show the reverted change did not alter it) |
| `reports/simulation_v2/results_rejected_restudy_leaves_no_trace.json` | restudy recorded as no memory trace at all | bug: a rule never retrieved never decayed (B recall 0.36 with zero retrievals in `own_sentences_0`) |
