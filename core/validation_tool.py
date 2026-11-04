"""Validation Tool: parses the LLM output and normalizes it against the active criteria.

Guarantees on the returned scorecard:
  * exactly one entry per active criterion, in criterion_id order
  * every score is a float within [0, max_score] taken from the DATABASE (not the LLM)
  * missing / malformed criteria are scored 0 and flagged
  * every correction is recorded as a human-readable warning
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

STATUS_OK = "ok"
STATUS_CLIPPED = "clipped"
STATUS_RESCALED = "rescaled"
STATUS_INVALID = "invalid_score"
STATUS_MISSING = "missing"
STATUS_UNGROUNDED = "ungrounded"


def parse_llm_json(raw: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Extract a JSON object from raw model text (tolerates code fences and leading prose)."""
    warnings: list[str] = []
    if raw is None or not str(raw).strip():
        return None, ["LLM returned an empty response."]
    text = str(raw).strip()

    fence = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S | re.I)
    if fence:
        text = fence.group(1).strip()
        warnings.append("LLM wrapped JSON in a markdown code fence; fence removed.")

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None, warnings + ["LLM output contained no JSON object."]
        try:
            obj = json.loads(text[start:end + 1])
            warnings.append("LLM output had extra text around the JSON; extracted the object.")
        except json.JSONDecodeError as exc:
            return None, warnings + [f"LLM output is not valid JSON ({exc.msg} at char {exc.pos})."]

    if not isinstance(obj, dict):
        return None, warnings + [f"LLM output JSON is a {type(obj).__name__}, expected an object."]
    return obj, warnings


def _to_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, str):
        m = re.search(r"-?\d+(?:\.\d+)?", value)  # "8", "8/10", "score: 7.5"
        return float(m.group()) if m else None
    return None


def _to_int(value: Any) -> int | None:
    num = _to_number(value)
    return int(num) if num is not None and float(num).is_integer() else None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


MIN_EVIDENCE_WORDS = 3          # "ISO" alone proves nothing; "ISO 27001 certified" can
UNGROUNDED_CAP = 0.5            # a claim the PDF doesn't back can earn at most half marks


def evidence_in_document(evidence: str, document_text: str, min_overlap: float = 0.6) -> bool:
    """Grounding check: is the quoted evidence (approximately) present in the document?"""
    ev, doc = _norm(evidence), _norm(document_text)
    words = ev.split()
    if len(words) < MIN_EVIDENCE_WORDS:
        return False
    if f" {ev} " in f" {doc} ":     # whole-word match only
        return True
    if len(words) < 4:
        return False
    # sliding 4-word shingles: share of evidence shingles found in the document
    shingles = [" ".join(words[i:i + 4]) for i in range(len(words) - 3)]
    found = sum(1 for s in shingles if s in doc)
    return found / len(shingles) >= min_overlap


def evidence_page(evidence: str, document_text: str) -> int | None:
    """Page number ([Page N] marker from the Document Tool) where the evidence best matches."""
    words = _norm(evidence).split()
    if len(words) < MIN_EVIDENCE_WORDS:
        return None
    probes = [" ".join(words[i:i + 4]) for i in range(max(len(words) - 3, 1))]
    best, best_hits = None, 0
    for num, body in re.findall(r"\[Page (\d+)\]\n?(.*?)(?=\[Page \d+\]|\Z)", document_text, flags=re.S):
        page = f" {_norm(body)} "
        hits = sum(1 for p in probes if p in page)
        if hits > best_hits:
            best, best_hits = int(num), hits
    return best


def validate_evaluation(parsed: dict[str, Any] | None, criteria: list[dict[str, Any]],
                        supplier_name: str, document_text: str = "") -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    parsed = parsed if isinstance(parsed, dict) else {}
    tag = f"[{supplier_name}]"

    returned_name = parsed.get("supplier_name")
    if returned_name and str(returned_name).strip().lower() != supplier_name.strip().lower():
        warnings.append(f"{tag} LLM returned supplier_name '{returned_name}'; replaced with the entered name.")

    raw_items = parsed.get("criteria")
    if raw_items is None:
        raw_items = []
        if parsed:
            warnings.append(f"{tag} 'criteria' field missing from LLM output.")
    elif not isinstance(raw_items, list):
        warnings.append(f"{tag} 'criteria' is not a list; ignored.")
        raw_items = []

    by_id = {int(c["criterion_id"]): c for c in criteria}
    by_name = {_norm(c["name"]): int(c["criterion_id"]) for c in criteria}
    matched: dict[int, dict[str, Any]] = {}

    for item in raw_items:
        if not isinstance(item, dict):
            warnings.append(f"{tag} Ignored a non-object entry in 'criteria'.")
            continue
        cid = _to_int(item.get("criterion_id"))
        if cid not in by_id:
            alt = by_name.get(_norm(str(item.get("name") or item.get("criterion") or "")))
            if alt is not None:
                warnings.append(f"{tag} Matched criterion by name instead of id ({item.get('criterion_id')!r} -> {alt}).")
                cid = alt
            else:
                warnings.append(f"{tag} Ignored result for unknown/inactive criterion_id {item.get('criterion_id')!r}.")
                continue
        if cid in matched:
            warnings.append(f"{tag} Duplicate result for criterion {cid}; kept the first one.")
            continue
        matched[cid] = item

    scorecard = []
    for c in criteria:
        cid, db_max, name = int(c["criterion_id"]), float(c["max_score"]), c["name"]
        item = matched.get(cid)
        entry: dict[str, Any] = {
            "criterion_id": cid,
            "name": name,
            "max_score": db_max,
            "score": 0.0,
            "raw_score": None,
            "justification": "",
            "evidence": "",
            "evidence_grounded": False,
            "evidence_page": None,
            "validation_status": STATUS_MISSING,
        }
        if item is None:
            entry["justification"] = "No valid result returned by the evaluator; scored 0 by policy."
            warnings.append(f"{tag} Criterion {cid} '{name}' missing from LLM output; scored 0.")
            scorecard.append(entry)
            continue

        entry["justification"] = str(item.get("justification") or "").strip() or "(no justification provided)"
        entry["evidence"] = str(item.get("evidence") or "").strip()
        raw_score = _to_number(item.get("score"))
        entry["raw_score"] = item.get("score")

        if raw_score is None:
            entry["validation_status"] = STATUS_INVALID
            warnings.append(f"{tag} Criterion {cid} '{name}' score {item.get('score')!r} is not numeric; scored 0.")
            scorecard.append(entry)
            continue

        score, status = raw_score, STATUS_OK
        llm_max = _to_number(item.get("max_score"))
        if llm_max and llm_max > 0 and abs(llm_max - db_max) > 1e-9 and 0 <= raw_score <= llm_max:
            score = raw_score / llm_max * db_max
            status = STATUS_RESCALED
            warnings.append(f"{tag} Criterion {cid} used max_score {llm_max:g} instead of {db_max:g}; "
                            f"rescaled {raw_score:g} -> {score:.2f}.")
        if score < 0 or score > db_max:
            clipped = min(max(score, 0.0), db_max)
            warnings.append(f"{tag} Criterion {cid} score {score:g} outside 0-{db_max:g}; clipped to {clipped:g}.")
            score, status = clipped, STATUS_CLIPPED

        if document_text:
            entry["evidence_grounded"] = evidence_in_document(entry["evidence"], document_text)
            entry["evidence_page"] = evidence_page(entry["evidence"], document_text)
            cap = db_max * UNGROUNDED_CAP
            if not entry["evidence_grounded"]:
                why = ("has no supporting evidence quote" if not entry["evidence"]
                       else "evidence could not be found in the document (possible paraphrase or hallucination)")
                if score > cap:
                    warnings.append(f"{tag} Criterion {cid} '{name}' {why}; score capped {score:g} -> {cap:g}.")
                    score, status = cap, STATUS_UNGROUNDED
                else:
                    warnings.append(f"{tag} Criterion {cid} '{name}' {why}.")

        entry["score"] = round(score, 2)
        entry["validation_status"] = status
        scorecard.append(entry)

    risks = parsed.get("risks", [])
    if isinstance(risks, str):
        risks = [risks]
    elif not isinstance(risks, list):
        risks = []
    risks = [str(r).strip() for r in risks if str(r).strip()]

    summary = parsed.get("overall_summary")
    summary = str(summary).strip() if summary else "(no summary returned)"

    return {
        "supplier_name": supplier_name,
        "criteria": scorecard,
        "risks": risks,
        "overall_summary": summary,
    }, warnings
