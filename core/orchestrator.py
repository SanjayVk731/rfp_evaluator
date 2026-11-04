"""Orchestrator Agent: runs the fixed tool sequence and records an auditable trace.

Setup -> Input checks -> Batch -> Evaluate (per supplier: extract, prompt, LLM) -> Validate
      -> Score -> Benchmark -> Rank -> Persist -> (Present happens in the UI)
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable

from . import db
from .document_tool import DocumentError, extract_text
from .evaluation_agent import LLMConfig, LLMError, evaluate_supplier
from .ranking_tool import rank_suppliers
from .validation_tool import parse_llm_json, validate_evaluation

EXPERIENCE_MIN, EXPERIENCE_MAX = 0.0, 5.0


@dataclass
class SupplierInput:
    supplier_name: str
    submission_date: str          # ISO yyyy-mm-dd
    experience_rating: float      # 0.0 - 5.0
    file_name: str
    file_bytes: bytes


class InputValidationError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def validate_inputs(suppliers: list[SupplierInput]) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors block the run; warnings are recorded."""
    errors: list[str] = []
    warnings: list[str] = []
    if not suppliers:
        return ["Upload at least one supplier PDF."], []
    if len(suppliers) == 1:
        warnings.append("Only one supplier: peer benchmarks will compare the supplier with itself (PPI = 100).")

    seen_names: dict[str, str] = {}
    seen_hashes: dict[str, str] = {}
    for i, s in enumerate(suppliers, start=1):
        label = s.file_name or f"row {i}"
        name = (s.supplier_name or "").strip()
        if not name:
            errors.append(f"{label}: supplier name is required.")
        elif name.casefold() in seen_names:
            errors.append(f"{label}: duplicate supplier name '{name}' (also used for {seen_names[name.casefold()]}).")
        else:
            seen_names[name.casefold()] = label

        try:
            d = date.fromisoformat(str(s.submission_date)[:10])
            if d > date.today():
                warnings.append(f"{label}: submission date {d} is in the future.")
        except ValueError:
            errors.append(f"{label}: submission date '{s.submission_date}' is not a valid YYYY-MM-DD date.")

        try:
            r = float(s.experience_rating)
            if not EXPERIENCE_MIN <= r <= EXPERIENCE_MAX:
                errors.append(f"{label}: experience rating {r} must be between {EXPERIENCE_MIN} and {EXPERIENCE_MAX}.")
        except (TypeError, ValueError):
            errors.append(f"{label}: experience rating must be a number.")

        if not s.file_name.lower().endswith(".pdf"):
            errors.append(f"{label}: only PDF files are accepted.")
        h = hashlib.sha256(s.file_bytes).hexdigest()
        if h in seen_hashes:
            warnings.append(f"{label}: identical file content to {seen_hashes[h]}.")
        else:
            seen_hashes[h] = label
    return errors, warnings


class Orchestrator:
    def __init__(self, llm: LLMConfig, db_path: str | None = None,
                 on_step: Callable[[str, str], None] | None = None):
        self.llm = llm
        self.db_path = db_path
        self.on_step = on_step or (lambda step, detail: None)
        self.trace: list[dict[str, Any]] = []

    def _log(self, step: str, tool: str, status: str, detail: str, started: float) -> None:
        entry = {"step": step, "tool": tool, "status": status, "detail": detail,
                 "duration_s": round(time.time() - started, 3)}
        self.trace.append(entry)
        self.on_step(step, f"{tool}: {detail}")

    def run(self, suppliers: list[SupplierInput]) -> dict[str, Any]:
        warnings: list[str] = []

        # 2. Input checks
        t = time.time()
        errors, input_warnings = validate_inputs(suppliers)
        if errors:
            self._log("Input", "InputValidator", "error", f"{len(errors)} blocking error(s)", t)
            raise InputValidationError(errors)
        warnings += input_warnings
        self._log("Input", "InputValidator", "ok", f"{len(suppliers)} supplier(s) accepted", t)

        # 3. Batch
        t = time.time()
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        run_id = f"RFP-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6].upper()}"

        # 4a. Reload active criteria (latest version, not what the UI showed earlier)
        criteria = db.get_active_criteria(self.db_path)
        ok, total = db.check_weights(criteria)
        if not ok:
            self._log("Batch", "CriteriaLoader", "error", f"active weights total {total}, expected 100", t)
            raise InputValidationError([f"Active criteria weights total {total}%, they must total 100%."])
        db.create_run(run_id, created_at, len(suppliers), self.llm.provider, self.llm.model, criteria, self.db_path)
        self._log("Batch", "BatchManager", "ok", f"{run_id} created with {len(criteria)} active criteria", t)

        try:
            # 4b-5. Evaluate + validate each supplier independently
            validated: list[dict[str, Any]] = []
            for s in suppliers:
                validated.append(self._evaluate_one(s, criteria, warnings))

            # 6-8. Score, benchmark, rank (deterministic)
            t = time.time()
            ranking = rank_suppliers(validated, criteria)
            self._log("Score/Benchmark/Rank", "RankingTool", "ok",
                      f"ranked {len(ranking['suppliers'])} supplier(s); leader "
                      f"{ranking['suppliers'][0]['supplier_name']}", t)

            status = "COMPLETED_WITH_WARNINGS" if warnings else "COMPLETED"
            result = {
                "rfp_run_id": run_id,
                "created_at": created_at,
                "status": status,
                "llm": {"provider": self.llm.provider, "model": self.llm.model,
                        "temperature": self.llm.temperature},
                "criteria": criteria,
                "formulas": {
                    "absolute_score": "sum(score/max_score * weight) / sum(weights) * 100",
                    "benchmark": "max score per criterion across suppliers",
                    "gap": "supplier score - benchmark",
                    "relative_pct": "supplier score / benchmark * 100 (0 if benchmark is 0)",
                    "ppi": "sum(relative_pct * weight) / sum(weights)",
                },
                **ranking,
                "warnings": warnings,
                "trace": self.trace,
            }

            # 9. Persist
            t = time.time()
            db.save_supplier_results(run_id, ranking["suppliers"], self.db_path)
            result["trace"] = self.trace + [{"step": "Persist", "tool": "SQLite", "status": "ok",
                                             "detail": f"{len(ranking['suppliers'])} rows + run JSON",
                                             "duration_s": round(time.time() - t, 3)}]
            db.update_run_status(run_id, status, warnings, result, self.db_path)
            self.trace = result["trace"]
            self.on_step("Persist", f"SQLite: saved run {run_id}")
            return result
        except Exception as exc:
            db.update_run_status(run_id, "FAILED", warnings + [f"Run failed: {exc}"], None, self.db_path)
            raise

    def _evaluate_one(self, s: SupplierInput, criteria: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
        name = s.supplier_name.strip()
        meta = {"supplier_name": name, "submission_date": str(s.submission_date)[:10],
                "experience_rating": float(s.experience_rating), "file_name": s.file_name}
        supplier_warnings: list[str] = []

        # Document Tool
        t = time.time()
        try:
            doc = extract_text(s.file_bytes, s.file_name)
            supplier_warnings += doc.warnings
            meta.update({"file_sha256": doc.sha256, "page_count": doc.page_count, "text_chars": doc.char_count})
            self._log("Evaluate", "DocumentTool", "ok", f"{name}: {doc.page_count} page(s), {doc.char_count} chars", t)
            text = doc.text if doc.body_chars >= 20 else ""
        except DocumentError as exc:
            supplier_warnings.append(str(exc))
            self._log("Evaluate", "DocumentTool", "error", f"{name}: {exc}", t)
            text = ""

        # Evaluation Agent
        raw = ""
        if text:
            t = time.time()
            try:
                out = evaluate_supplier(self.llm, name, criteria, text)
                raw = out["raw"]
                self._log("Evaluate", "EvaluationAgent", "ok",
                          f"{name}: {self.llm.model} responded in {out['elapsed_s']}s", t)
            except LLMError as exc:
                # An outage must not look like a weak proposal: fail the whole run instead of scoring 0.
                self._log("Evaluate", "EvaluationAgent", "error", f"{name}: {exc}", t)
                raise LLMError(f"Evaluation of {name} failed, so no ranking was produced: {exc}") from exc
        else:
            supplier_warnings.append(f"[{name}] No document text - evaluator skipped; all criteria scored 0.")

        # Validation Tool
        t = time.time()
        parsed, parse_warnings = parse_llm_json(raw) if raw else (None, [])
        supplier_warnings += [f"[{name}] {w}" for w in parse_warnings]
        scorecard, val_warnings = validate_evaluation(parsed, criteria, name, text)
        supplier_warnings += val_warnings
        self._log("Validate", "ValidationTool", "warn" if val_warnings or parse_warnings else "ok",
                  f"{name}: {len(val_warnings) + len(parse_warnings)} correction(s)", t)

        warnings.extend(supplier_warnings)
        return {**meta, **scorecard, "warnings": supplier_warnings, "llm_raw_output": raw[:20000]}
