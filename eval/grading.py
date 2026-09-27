"""
Pure grading and summary functions for the eval, kept free of API and config
imports so they can be unit-tested (tests/test_eval_grading.py).

Verdict "sides" and order are a convention for measuring instability, not a
claim that the scale is ordinal: NOT_VIABLE is the negative side, VIABLE and
VIABLE_IF the positive side, RISKY and NEEDS_VALIDATION the middle.
"""

import math
from collections import Counter
from itertools import combinations

VERDICTS = ("NOT_VIABLE", "RISKY", "NEEDS_VALIDATION", "VIABLE_IF", "VIABLE")
VERDICT_ORDER = {v: i for i, v in enumerate(VERDICTS)}
SIDE = {"NOT_VIABLE": "negative", "RISKY": "middle", "NEEDS_VALIDATION": "middle",
        "VIABLE_IF": "positive", "VIABLE": "positive"}


# --- grading one attempt ---------------------------------------------------

def grade_gate(decision: str, injection_suspected: bool, expected: list[str],
               expect_injection: bool = False) -> dict:
    rejected = decision != "ANALYZABLE"
    return {
        "correct": int(decision in expected),
        "false_reject": int("ANALYZABLE" in expected and rejected),
        "false_accept": int("ANALYZABLE" not in expected and not rejected),
        "injection_ok": int(injection_suspected == expect_injection),
    }


# Cost of answering `answer` when the case's primary verdict is `truth`. Asymmetric
# on purpose: missing a blocker (a positive answer to a not-viable idea) costs far
# more than erring on the cautious side. The numbers are a starting convention from
# the 2026-09-27 review, to be revisited, not a measured loss.
ERROR_COST = {
    "NOT_VIABLE":       {"NOT_VIABLE": 0, "RISKY": 2, "NEEDS_VALIDATION": 2, "VIABLE_IF": 5, "VIABLE": 5},
    "RISKY":            {"NOT_VIABLE": 1, "RISKY": 0, "NEEDS_VALIDATION": 1, "VIABLE_IF": 2, "VIABLE": 3},
    "NEEDS_VALIDATION": {"NOT_VIABLE": 2, "RISKY": 1, "NEEDS_VALIDATION": 0, "VIABLE_IF": 1, "VIABLE": 2},
    "VIABLE_IF":        {"NOT_VIABLE": 3, "RISKY": 1, "NEEDS_VALIDATION": 1, "VIABLE_IF": 0, "VIABLE": 1},
    "VIABLE":           {"NOT_VIABLE": 4, "RISKY": 2, "NEEDS_VALIDATION": 1, "VIABLE_IF": 1, "VIABLE": 0},
}


def allowed_verdicts(case: dict) -> list[str]:
    """The primary verdict plus its acceptable neighbours."""
    return [case["primary"], *case.get("acceptable", [])]


def grade_pipeline(verdict: str, case: dict, consistency_warnings: list[str],
                   lens_statuses: list[str]) -> dict:
    """
    primary_hit: the verdict is the case's primary verdict (the headline metric)
    in_range: the verdict is the primary one or an acceptable neighbour
    error_cost: ERROR_COST of this verdict against the primary one (lower is better)
    """
    return {
        "primary_hit": int(verdict == case["primary"]),
        "in_range": int(verdict in allowed_verdicts(case)),
        "error_cost": ERROR_COST[case["primary"]][verdict],
        "consistent": int(not consistency_warnings),
        "all_lenses_ok": int(all(status == "success" for status in lens_statuses)),
    }


def rescore(rows: list[dict], cases: dict[str, dict]) -> list[dict]:
    """
    Regrade stored pipeline rows against the current case labels, so a run made
    under old labels can be compared with new runs. Rows of cases that no longer
    exist are dropped; the stored verdict, lens results and costs are kept.
    """
    rescored = []
    for row in rows:
        case = cases.get(row["prompt_id"])
        if case is None:
            continue
        grade = {**row["grade"], **{k: v for k, v in grade_pipeline(
            row["meta"]["verdict"], case, [], []).items() if k in ("primary_hit", "in_range", "error_cost")}}
        meta = {**row["meta"], "primary": case["primary"], "acceptable": case.get("acceptable", []),
                "expected": allowed_verdicts(case)}
        rescored.append({**row, "grade": grade, "meta": meta})
    return rescored


def wilson(passes: int, n: int) -> tuple[float, float]:
    """95% Wilson score interval for a pass rate."""
    if n == 0:
        return 0.0, 0.0
    z, p = 1.96, passes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


# --- reference baselines ---------------------------------------------------

def constant_baselines(expected_per_row: list[list[str]]) -> dict:
    """
    What trivial answerers would score on the same attempts: always giving one
    verdict, and picking a verdict uniformly at random (expected value). A metric
    that does not clearly beat these measures little.
    """
    n = len(expected_per_row)
    always = {v: sum(v in expected for expected in expected_per_row) for v in VERDICTS}
    random_hits = sum(len(set(expected) & set(VERDICTS)) / len(VERDICTS) for expected in expected_per_row)
    return {"n": n, "always": always, "random": random_hits}


def labelled_baselines(primaries: list[str]) -> dict:
    """
    Trivial answerers against primary labels: per constant verdict, primary hits
    and mean error cost; for a uniformly random verdict, the expected values.
    """
    n = len(primaries)
    if not n:
        return {"n": 0, "always": {}, "random": {"primary_hits": 0.0, "mean_cost": 0.0}}
    always = {
        v: {"primary_hits": sum(p == v for p in primaries),
            "mean_cost": sum(ERROR_COST[p][v] for p in primaries) / n}
        for v in VERDICTS
    }
    random = {"primary_hits": n / len(VERDICTS),
              "mean_cost": sum(sum(ERROR_COST[p].values()) / len(VERDICTS) for p in primaries) / n}
    return {"n": n, "always": always, "random": random}


# --- stability across reps -------------------------------------------------

def _by_case(rows: list[dict]) -> dict[str, list[dict]]:
    cases: dict[str, list[dict]] = {}
    for row in rows:
        cases.setdefault(row["prompt_id"], []).append(row)
    return cases


def stability(rows: list[dict]) -> dict:
    """
    How much the overall verdict moves between reps of the same case. Only cases
    with at least two reps count.

    modal_agreement: share of attempts that gave their case's most common verdict
    changed_cases: cases with more than one distinct verdict
    cross_side_cases: cases whose reps reach both the negative and the positive side
    pairwise_disagreement: share of pairs of reps with different verdicts, averaged over
        cases; unlike changed_cases it does not grow with the number of reps
    mean_ordinal_spread: mean pairwise distance between reps' verdicts, averaged over cases
    """
    cases = {k: v for k, v in _by_case(rows).items() if len(v) > 1}
    attempts = modal = 0
    changed, cross_side, spreads, disagreements = [], [], [], []
    for case_id, case_rows in sorted(cases.items()):
        verdicts = [r["meta"]["verdict"] for r in case_rows]
        counts = Counter(verdicts)
        attempts += len(verdicts)
        modal += counts.most_common(1)[0][1]
        if len(counts) > 1:
            changed.append(case_id)
        sides = {SIDE[v] for v in verdicts}
        if {"negative", "positive"} <= sides:
            cross_side.append(case_id)
        pairs = list(combinations(verdicts, 2))
        disagreements.append(sum(a != b for a, b in pairs) / len(pairs))
        spreads.append(sum(abs(VERDICT_ORDER[a] - VERDICT_ORDER[b]) for a, b in pairs) / len(pairs))
    return {
        "cases": len(cases),
        "attempts": attempts,
        "modal_agreement": modal / attempts if attempts else 0.0,
        "changed_cases": changed,
        "cross_side_cases": cross_side,
        "pairwise_disagreement": sum(disagreements) / len(disagreements) if disagreements else 0.0,
        "mean_ordinal_spread": sum(spreads) / len(spreads) if spreads else 0.0,
    }


def calibration(rows: list[dict]) -> dict[str, dict]:
    """
    Per synthesis confidence level: attempts, how many were in range, and how many
    belong to a case whose reps all gave the same verdict. A useful HIGH is both
    more often right and more often stable than MEDIUM and LOW.
    """
    cases = _by_case(rows)
    unanimous = {k: len({r["meta"]["verdict"] for r in v}) == 1 for k, v in cases.items() if len(v) > 1}
    result = {}
    for level in ("HIGH", "MEDIUM", "LOW"):
        level_rows = [r for r in rows if r["meta"]["confidence"] == level]
        if not level_rows:
            continue
        comparable = [r for r in level_rows if r["prompt_id"] in unanimous]
        result[level] = {
            "n": len(level_rows),
            "in_range": sum(r["grade"]["in_range"] for r in level_rows),
            "comparable": len(comparable),
            "all_reps_agree": sum(unanimous[r["prompt_id"]] for r in comparable),
        }
    return result


def lens_flip_rates(rows: list[dict]) -> dict[str, tuple[int, int]]:
    """Per lens: (cases where its verdict changed between reps, cases it ran in every rep)."""
    rates: dict[str, list[int]] = {}
    for case_rows in _by_case(rows).values():
        if len(case_rows) < 2:
            continue
        lens_names = set.intersection(*(set(r["meta"].get("lens_verdicts", {})) for r in case_rows))
        for lens in lens_names:
            verdicts = {r["meta"]["lens_verdicts"][lens] for r in case_rows}
            flipped, total = rates.setdefault(lens, [0, 0])
            rates[lens] = [flipped + (len(verdicts) > 1), total + 1]
    return {lens: (flipped, total) for lens, (flipped, total) in sorted(rates.items())}
