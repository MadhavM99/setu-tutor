"""Results tables (TASKS.md tasks 20, 23): built only from saved reports, with Wilson intervals."""
from setu.research import results_tables


def test_a_rate_gets_its_wilson_interval_and_a_missing_rate_says_so():
    assert results_tables.ci(21 / 29, 29) == "0.72 [0.54, 0.85]"
    assert results_tables.ci(0.0, 29) == "0.00 [0.00, 0.12]"
    assert results_tables.ci(None, 29) == "n/a" and results_tables.ci(0.5, 0) == "n/a"


def test_missing_reports_are_named_not_invented(tmp_path, monkeypatch):
    monkeypatch.setattr(results_tables, "REPORTS", tmp_path)
    text = results_tables.build()
    assert "## task 6: no run report yet" in text and "## task 18: no run report yet" in text
    assert "| **total** |  | **0** | **0** |" in text
