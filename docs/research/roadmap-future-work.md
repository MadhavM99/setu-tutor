# Roadmap: every future-work item from the paper (§11) and prompt §15

**None of these is a first-milestone commitment.** Each entry lists:
- **Spec** — what would be built;
- **RQ** — the research question;
- **Deps** — dependencies;
- **Risks**;
- **Gate** — what must hold before work starts or learners are exposed;
- **Eval** — how it is evaluated.

All items are tagged **[P]**. FW-P23 is pulled into the first release as **[X-BEG]**.

## Research

### FW-R01 Larger controlled trial
- **Spec:** A vs B vs C over several delayed tests (1 week, 1 month), with factorial arms to separate teaching the peer, explaining the rule, feedback, and extra retrieval.
- **RQ:** Where does any benefit come from?
- **Deps:** pilot; power analysis.
- **Risks:** recruitment; attrition.
- **Gate:** pilot complete; preregistration; ethics.
- **Eval:** mixed models with learners and rules as random effects; Hedges' g.

### FW-R02 Learner-error collection at scale
- **Spec:** exam scripts, assignments and writing from many adults; independent annotation with κ; unexpected errors kept.
- **RQ:** What errors do learners in each direction really make?
- **Deps:** institutional permissions; F5 upload.
- **Risks:** privacy; annotation cost.
- **Gate:** ethics approval; anonymisation pipeline tested.
- **Eval:** κ ≥ 0.6; coverage of the contrast table.

### FW-R03 Each direction separately
- **Spec:** does the same contrast give different error patterns TE→HI vs HI→TE, and does a contrast-based model beat a general GEC baseline?
- **RQ:** Is transfer asymmetric?
- **Deps:** FW-R02 data in both directions.
- **Risks:** too little TE→HI data.
- **Gate:** observed data in both directions.
- **Eval:** precision and recall per direction vs baselines.

### FW-R04 Checker robustness
- **Spec:** spelling variation, morphology (analyser), alternative constructions, regional forms, ambiguity, abstention policy.
- **RQ:** When should the checker abstain?
- **Deps:** analyser evaluated on 50 sentences; IndicGEC.
- **Risks:** false accepts.
- **Gate:** M-07 holds.
- **Eval:** M-07/08/09 and M-55; κ vs teachers.

### FW-R05 Forgetting vs remembering classmate; feedback types
- **Spec:** equal-practice comparison; recasts, L1 rules, explicit contrasts, guided self-correction by band and direction.
- **RQ:** Does forgetting-driven re-teaching add value?
- **Deps:** Stage A gates.
- **Risks:** confounds with exposure count.
- **Gate:** G2.
- **Eval:** delayed production; matched exposures.

### FW-R06 Feedback style
- **Spec:** direct correction vs a short Hindi explanation vs an explicit Hindi–Telugu contrast, at matched difficulty.
- **RQ:** Which feedback transfers best?
- **Deps:** coach gates.
- **Risks:** the learner's preference ≠ learning.
- **Gate:** M-18, M-20.
- **Eval:** transfer test, not perceived helpfulness.

### FW-R07 Adaptive error-profile diagnostic
- **Spec:** estimate a learner's weak rules from several attempts to seed the planner and classmate.
- **RQ:** Does a profile shorten time to mastery?
- **Deps:** the tracker (M-23).
- **Risks:** over-testing.
- **Gate:** the tracker beats BKT.
- **Eval:** M-52, M-53.

### FW-R08 Teacher error-to-lesson pipeline
- **Spec:** upload → proposed spans and rules → teacher approval → bank.
- **RQ:** How much teacher time does it save?
- **Deps:** F5.
- **Risks:** privacy; false proposals.
- **Gate:** privacy review.
- **Eval:** teacher minutes per approved rule; precision of proposals.

### FW-R09 The learner's own errors
- **Spec:** the classmate replays this learner's past wrong forms instead of bank errors.
- **RQ:** Does correcting one's own mistake "in someone else's mouth" help more?
- **Deps:** copy-rate data.
- **Risks:** reinforcing errors.
- **Gate:** M-37 < 5%.
- **Eval:** delayed production by rule.

### FW-R10 When the classmate appears
- **Spec:** start threshold of 1 / 3 / 5 rules; an adaptive switch.
- **RQ:** When should the learner become the tutor?
- **Deps:** X-CLS-START.
- **Risks:** beginners overwhelmed.
- **Gate:** simulation ablation first.
- **Eval:** retention and dropout.

### FW-R11 Confidence and calibration
- **Spec:** confidence before each fix.
- **RQ:** Does teaching narrow the gap between confidence and delayed production?
- **Deps:** the X-EXCH-03 flag.
- **Risks:** extra burden.
- **Gate:** usability check.
- **Eval:** calibration curves.

### FW-R12 Validated simulated learners
- **Spec:** fit forgetting and error rates to pilot data; predict the next cohort.
- **RQ:** Can simulation screen designs?
- **Deps:** pilot data.
- **Risks:** overfitting.
- **Gate:** pilot complete.
- **Eval:** predictive error on the next cohort.

### FW-R13 Long-term and real-world outcomes
- **Spec:** retention at 1–3 months; a task with a native speaker (directions, bargaining).
- **RQ:** Does it last and transfer to real use?
- **Deps:** FW-R01.
- **Risks:** attrition.
- **Gate:** ethics.
- **Eval:** task success rubric.

### FW-R14 Four-dimension leveler, L0–L5 can-do descriptors, Telugu learner scale
- **Spec:** max, weighted and fitted levelers; validated against teacher bands; for Hindi, compared against the CEFR labels of ReadMe++; a learner-facing Telugu scale (none exists).
- **RQ:** Which leveler predicts comprehension?
- **Deps:** teacher band labels.
- **Risks:** few labels.
- **Gate:** M-51 κ ≥ 0.6 before any claim.
- **Eval:** κ; comprehension AUC.

### FW-R15 Weak classmate by other means
- **Spec:** external state vs machine unlearning vs fine-tuned learner models.
- **RQ:** Cost and safety trade-offs.
- **Deps:** M-01/M-02 baselines.
- **Risks:** compute.
- **Gate:** G2.
- **Eval:** M-01, M-02, cost.

### FW-R16 Fairness
- **Spec:** leveler and checker behaviour by script familiarity, schooling, exposure, region.
- **RQ:** Are some learners disadvantaged?
- **Deps:** background data.
- **Risks:** small subgroups.
- **Gate:** n per subgroup ≥ 10.
- **Eval:** error-rate gaps with CIs.

### FW-R17 Personalisation study
- **Spec:** history-driven rule selection, difficulty, intervals and hint depth vs a fixed sequence; transparent tracker vs richer knowledge tracing.
- **RQ:** Does personalisation help?
- **Deps:** the tracker.
- **Risks:** complexity.
- **Gate:** M-23.
- **Eval:** time to mastery; retention.

## Product

### FW-P18 Released dataset
- **Spec:** verified errors, corrections, rule descriptions, evaluation items; licensing, privacy, access control, annotation process.
- **Deps:** licences (LTRC commercial use).
- **Risks:** licence breach.
- **Gate:** licences confirmed; consent scope `data_sharing`.
- **Eval:** datasheet completeness.

### FW-P19 Classroom deployment
- **Spec:** teacher-led studies, incl. classes 6–10; dashboards; observed vs estimated; override.
- **Deps:** F6, F7.
- **Risks:** child data.
- **Gate:** parental consent, child assent, DPDP Act compliance, school approval.
- **Eval:** teacher adoption; learning outcomes.

### FW-P20 Per-sound pronunciation scoring
- **Spec:** forced alignment for ళ, short ఎ/ఒ, word-final u; ASR tuned on Hindi-accented Telugu.
- **Deps:** speech gate.
- **Risks:** wrong feedback on sounds.
- **Gate:** sound-check κ ≥ 0.6 vs teachers (M-26).
- **Eval:** κ; learner improvement.

### FW-P21 Activation steering
- **Spec:** a contrastive activation-addition vector moves the friend's speech toward spoken Hyderabad Telugu and keeps the classmate's persona; ablation vs prompting and reranking; **never decides correctness**; a working vector is distilled into a LoRA for serving.
- **Deps:** the friend gate; a self-hosted model.
- **Risks:** drift.
- **Gate:** G-friend.
- **Eval:** M-45, M-03, M-21.

### FW-P22 Fine-tuning
- **Spec:** LoRA for spoken dialogue; DPO for coach hints on teacher-approved logs only.
- **Deps:** privacy review of logs.
- **Risks:** leaking learner text.
- **Gate:** consent scope; anonymisation.
- **Eval:** M-18, M-20, M-45.

### FW-P23 Hindi head start
- **Spec:** twins in varnamala order; new letters marked; Sanskrit-origin words; false friends.
- **Status:** **pulled into Phase 3** (X-BEG-01/02).

### FW-P24 Content factory
- **Spec:** state-textbook chapters → graded chunks with Hindi glosses, optional romanisation (approved), lexicon and analyser checks; failures wait for a teacher; no copyrighted sentences without permission.
- **Deps:** publisher permission.
- **Risks:** copyright.
- **Gate:** written permission.
- **Eval:** teacher acceptance rate.

### FW-P25 Shared weak-student benchmark
- **Spec:** release the leak and planting tests for other models and pairs.
- **Deps:** a stable Stage A suite.
- **Risks:** test contamination.
- **Gate:** held-out kept private.
- **Eval:** adoption.

### FW-P26 Human tandem pairs
- **Spec:** Telugu speakers learning Hindi matched with Hindi speakers learning Telugu; the checker moderates.
- **Deps:** the TE→HI direction working end to end.
- **Risks:** safety of peer chat.
- **Gate:** TE→HI gates; moderation policy.
- **Eval:** both partners' outcomes.

### FW-P27 Local varieties
- **Spec:** Hyderabadi Telugu, Dakhini Hindi, code-mixing.
- **Deps:** local speakers' variant lists.
- **Risks:** accepting errors as variants.
- **Gate:** variants approved by 2 local speakers.
- **Eval:** M-08 on variety samples.

### FW-P28 Low-cost deployment
- **Spec:** smaller models (Gemma 3 4B) and on-device inference.
- **Deps:** M-01/M-02 at 4B.
- **Risks:** leaks.
- **Gate:** G2 at the small model.
- **Eval:** M-01, M-02, cost per learner.

### FW-P29 More pairs
- **Spec:** Hindi↔Tamil, Hindi↔Kannada; which modules carry over.
- **Deps:** a stable pipeline for one pair.
- **Risks:** assuming transfer.
- **Gate:** the pair's own content gate.
- **Eval:** per-pair Stage A.
