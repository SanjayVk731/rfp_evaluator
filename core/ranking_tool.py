"""Ranking Tool: deterministic Python only - no LLM involvement.

Formulas (criteria iterated in criterion_id order so float sums are reproducible):
  absolute_score      = sum(score_c / max_c * weight_c) / sum(weight_c) * 100
  benchmark_c         = max(score_c over all suppliers)
  gap_c               = score_c - benchmark_c              (0 for the leader, otherwise negative)
  relative_pct_c      = score_c / benchmark_c * 100        (0.0 when benchmark_c == 0, flagged)
  PPI                 = sum(relative_pct_c * weight_c) / sum(weight_c)

Tie-break order (stable sort, then ranks 1..n assigned sequentially):
  1) higher PPI  2) earlier submission date  3) higher experience rating  4) supplier name ascending
"""
from __future__ import annotations

from datetime import date
from typing import Any

DECIMALS = 4  # every comparison uses values rounded to this precision


def _r(x: float) -> float:
    return round(float(x) + 0.0, DECIMALS)


def _parse_date(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def absolute_score(scorecard: list[dict[str, Any]], weights: dict[int, float]) -> float:
    total_w = sum(weights.values())
    if total_w <= 0:
        return 0.0
    pts = sum(c["score"] / c["max_score"] * weights[c["criterion_id"]] for c in scorecard)
    return _r(pts / total_w * 100)


def compute_benchmarks(suppliers: list[dict[str, Any]], criteria: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    benchmarks: dict[int, dict[str, Any]] = {}
    for c in criteria:
        cid = int(c["criterion_id"])
        scores = [(s["supplier_name"], _score_of(s, cid)) for s in suppliers]
        best = max((v for _, v in scores), default=0.0)
        leaders = sorted(name for name, v in scores if _r(v) == _r(best))
        benchmarks[cid] = {"criterion_id": cid, "name": c["name"], "benchmark_score": _r(best),
                           "leaders": leaders, "benchmark_zero": _r(best) == 0.0}
    return benchmarks


def _score_of(supplier: dict[str, Any], cid: int) -> float:
    for c in supplier["criteria"]:
        if c["criterion_id"] == cid:
            return float(c["score"])
    return 0.0


def sort_key(s: dict[str, Any]) -> tuple:
    return (-_r(s["ppi"]), _parse_date(s["submission_date"]), -_r(s["experience_rating"]),
            s["supplier_name"].casefold(), s["supplier_name"])


def _decisive_rule(a: dict[str, Any], b: dict[str, Any]) -> str:
    """Explain why supplier a is ranked directly above supplier b."""
    if _r(a["ppi"]) != _r(b["ppi"]):
        return f"higher PPI ({a['ppi']:.2f} vs {b['ppi']:.2f})"
    da, db_ = _parse_date(a["submission_date"]), _parse_date(b["submission_date"])
    if da != db_:
        return f"PPI tied at {a['ppi']:.2f}; earlier submission date ({da.isoformat()} vs {db_.isoformat()})"
    if _r(a["experience_rating"]) != _r(b["experience_rating"]):
        return (f"PPI and submission date tied; higher experience rating "
                f"({a['experience_rating']:g} vs {b['experience_rating']:g})")
    return "PPI, submission date and experience rating all tied; supplier name in ascending order"


def rank_suppliers(validated: list[dict[str, Any]], criteria: list[dict[str, Any]]) -> dict[str, Any]:
    """Takes validated scorecards + supplier metadata; returns ranked suppliers, benchmarks and explanations.

    Each item in `validated` needs: supplier_name, submission_date, experience_rating, criteria (scorecard).
    The input is not mutated.
    """
    criteria = sorted(criteria, key=lambda c: int(c["criterion_id"]))
    weights = {int(c["criterion_id"]): float(c["weight"]) for c in criteria}
    total_w = sum(weights.values())
    benchmarks = compute_benchmarks(validated, criteria)

    enriched = []
    for s in validated:
        rows = []
        for c in criteria:
            cid = int(c["criterion_id"])
            base = next(x for x in s["criteria"] if x["criterion_id"] == cid)
            score, bench = float(base["score"]), benchmarks[cid]["benchmark_score"]
            rel = 0.0 if bench == 0 else _r(score / bench * 100)
            rows.append({
                **base,
                "weight": weights[cid],
                "weighted_points": _r(score / float(base["max_score"]) * weights[cid]),
                "benchmark": bench,
                "gap": _r(score - bench),
                "relative_pct": rel,
                "is_benchmark_leader": _r(score) == bench and bench > 0,
            })
        ppi = _r(sum(r["relative_pct"] * r["weight"] for r in rows) / total_w) if total_w > 0 else 0.0
        enriched.append({**s, "criteria": rows, "absolute_score": absolute_score(rows, weights), "ppi": ppi})

    ordered = sorted(enriched, key=sort_key)  # Python's sort is stable
    explanations = []
    for i, s in enumerate(ordered):
        s["final_rank"] = i + 1
        if i > 0:
            prev = ordered[i - 1]
            rule = _decisive_rule(prev, s)
            s["rank_reason"] = f"Below {prev['supplier_name']}: {rule}."
            explanations.append(f"#{i} {prev['supplier_name']} above #{i + 1} {s['supplier_name']}: {rule}.")
        else:
            s["rank_reason"] = "Highest PPI after applying the tie-break order."

    return {
        "suppliers": ordered,
        "benchmarks": list(benchmarks.values()),
        "tie_break_explanation": explanations,
        "tie_break_order": ["Higher PPI", "Earlier submission date", "Higher historical experience rating",
                            "Supplier name ascending"],
    }
