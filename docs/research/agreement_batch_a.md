# Batch A Human-System Agreement Evaluation (Task 13)

## Executive Summary

- **Evaluated Batch**: Batch A (50 Telugu learner correction rows)
- **Annotator**: Native Telugu speaker (blinded human teacher)
- **Comparator**: Rule-based deterministic checker (`checker-1`)
- **Matched Examples (N)**: `50`
- **Observed Agreement ($p_o$)**: `0.3600` (36.0%)
- **Expected Chance Agreement ($p_e$)**: `0.2472` (24.7%)
- **Cohen's Kappa ($\kappa$)**: `0.1498`
- **Release Gate Target (M-16)**: `min 0.60`
- **Gate Outcome**: **FAIL** (observed $\kappa = 0.1498$ vs target $\ge 0.60$)

## 4x4 Confusion Matrix

| Human Teacher \ Checker | Correct | Partial | Wrong | Unsure | Total Human |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Correct** | 8 | 6 | 2 | 0 | **16** |
| **Partial** | 9 | 3 | 5 | 9 | **26** |
| **Wrong** | 0 | 0 | 7 | 1 | **8** |
| **Unsure** | 0 | 0 | 0 | 0 | **0** |
| **Total Checker** | **17** | **9** | **14** | **10** | **50** |

## Per-Category Performance

| Category | Human Count | Checker Count | Agreements | Precision | Recall |
|:---|:---:|:---:|:---:|:---:|:---:|
| `correct` | 16 | 17 | 8 | 47.1% | 50.0% |
| `partial` | 26 | 9 | 3 | 33.3% | 11.5% |
| `wrong` | 8 | 14 | 7 | 50.0% | 87.5% |
| `unsure` | 0 | 10 | 0 | 0.0% | N/A |

## Linguistic & Error Analysis

1. **High Specificity on `wrong`**:
   - When the human teacher judged an answer as `wrong` (8 rows), the deterministic checker caught 7 as `wrong` and 1 as `unsure`.
   - The checker generated **0 false passes** on human-judged wrong answers (0 marked as `correct` or `partial`).

2. **Divergence on `partial` and Colloquial Phrasing**:
   - The human teacher classified 26 examples as `partial`, noting pro-drop nuances, informal spoken registers, or minor omission slips.
   - The deterministic checker classified 9 of these as `unsure` (deferring to a teacher as intended by system design) and 9 as `correct` (where accepted variants matched).

3. **Conservative `unsure` Strategy**:
   - The checker returned `unsure` 10 times across Batch A, whereas the human native speaker committed to a substantive verdict in all 50 cases.

