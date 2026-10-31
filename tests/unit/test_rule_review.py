"""Rule review decisions and rater agreement (slice 4.2; F1, F2, P-EVAL-11, X-TCH-02/03, M-29, TS-TCH-REV-*,
TS-TCH-KAPPA)."""
import pytest

from setu.domain import rule_review as R
from setu.research import agreement as A


def rv(who, decision="approve", category=True, language="te", native=True):
    return R.Review(who, language, decision, category, native)


def test_one_native_approval_is_not_enough():
    assert R.decide([rv("a")]).state == "pending"


def test_two_agreeing_native_approvals_verify():
    d = R.decide([rv("a"), rv("b")])
    assert d.state == "verify" and d.approvers == ("a", "b")


@pytest.mark.parametrize("second", [rv("b", category=False), rv("b", decision="reject")])
def test_disagreement_between_two_reviewers_needs_a_third(second):
    assert R.decide([rv("a"), second]).state == "needs_third"


def test_the_third_reviewer_settles_it_by_majority():
    assert R.decide([rv("a"), rv("b", category=False), rv("c")]).state == "verify"
    assert R.decide([rv("a"), rv("b", decision="reject"), rv("c", decision="reject")]).state == "reject"
    assert R.decide([rv("a"), rv("b", category=False), rv("c", category=False)]).state == "needs_third"


def test_two_rejections_reject_and_uncertain_waits():
    assert R.decide([rv("a", decision="reject"), rv("b", decision="reject")]).state == "reject"
    assert R.decide([rv("a"), rv("b", decision="uncertain")]).state == "pending"


def test_only_native_telugu_reviews_count_for_validity():
    assert R.decide([rv("a"), rv("b", native=False)]).state == "pending"
    assert R.decide([rv("a"), rv("b", language="hi")]).state == "pending"


# ---------------------------------------------------------------- Cohen's kappa


def test_kappa_matches_a_hand_computed_reference():
    a = [1, 1, 0, 0, 1, 0, 1, 1, 0, 1]
    b = [1, 0, 0, 0, 1, 0, 1, 1, 1, 1]
    # po = 0.8, pe = 0.6*0.6 + 0.4*0.4 = 0.52, kappa = 0.28 / 0.48
    assert A.cohen_kappa(a, b) == pytest.approx(0.583333, abs=1e-3)


def test_kappa_for_nominal_labels_and_degenerate_cases():
    assert A.cohen_kappa(["L1", "L2", "L3"], ["L1", "L2", "L3"]) == pytest.approx(1.0)
    assert A.cohen_kappa(["L4"] * 5, ["L4"] * 5) is None  # chance agreement is 1: undefined
    with pytest.raises(ValueError):
        A.cohen_kappa([1, 0], [1])


def test_kappa_is_withheld_below_the_minimum_sample():
    r = A.report([1] * 9, [1] * 9)
    assert r.kappa is None and r.n == 9 and r.reason == "too_few"
    assert A.report([1, 0] * 5, [1, 0] * 5).kappa == pytest.approx(1.0)
