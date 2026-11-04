"""SQLite persistence: evaluation criteria, RFP runs and supplier results."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.environ.get("RFP_DB_PATH", os.path.join(PROJECT_ROOT, "data", "rfp_evaluation.db"))

WEIGHT_TOLERANCE = 0.01  # active weights must total 100 within this tolerance

DEFAULT_CRITERIA: list[dict[str, Any]] = [
    {
        "criterion_id": 1,
        "name": "Technical Capability",
        "description": "Solution architecture, integrations with existing systems, scalability, performance and overall technical fit.",
        "weight": 30.0,
        "max_score": 10,
        "is_active": 1,
    },
    {
        "criterion_id": 2,
        "name": "Implementation Plan",
        "description": "Timeline realism, milestones, staffing and team structure, delivery methodology and risk management plan.",
        "weight": 20.0,
        "max_score": 10,
        "is_active": 1,
    },
    {
        "criterion_id": 3,
        "name": "Commercial Value",
        "description": "Pricing clarity, total cost of ownership, stated assumptions, payment terms and value for money.",
        "weight": 20.0,
        "max_score": 10,
        "is_active": 1,
    },
    {
        "criterion_id": 4,
        "name": "Security & Compliance",
        "description": "Security controls, certifications (e.g. ISO 27001, SOC 2), data privacy, auditability and regulatory compliance.",
        "weight": 20.0,
        "max_score": 10,
        "is_active": 1,
    },
    {
        "criterion_id": 5,
        "name": "Support & Experience",
        "description": "Support model and SLAs, relevant similar projects, client references and track record.",
        "weight": 10.0,
        "max_score": 10,
        "is_active": 1,
    },
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluation_criteria (
    criterion_id INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL UNIQUE,
    description  TEXT    NOT NULL,
    weight       REAL    NOT NULL CHECK (weight >= 0 AND weight <= 100),
    max_score    INTEGER NOT NULL DEFAULT 10 CHECK (max_score > 0),
    is_active    INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS rfp_runs (
    rfp_run_id        TEXT PRIMARY KEY,
    created_at        TEXT NOT NULL,
    status            TEXT NOT NULL,
    supplier_count    INTEGER,
    llm_provider      TEXT,
    llm_model         TEXT,
    criteria_snapshot TEXT,
    warnings          TEXT,
    run_json          TEXT
);

CREATE TABLE IF NOT EXISTS supplier_results (
    result_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    rfp_run_id        TEXT    NOT NULL REFERENCES rfp_runs (rfp_run_id) ON DELETE CASCADE,
    supplier_name     TEXT    NOT NULL,
    submission_date   TEXT    NOT NULL,
    experience_rating REAL    NOT NULL,
    absolute_score    REAL,
    ppi               REAL,
    final_rank        INTEGER,
    result_json       TEXT    NOT NULL,
    UNIQUE (rfp_run_id, supplier_name)
);
"""


@contextmanager
def get_conn(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str | None = None, seed: bool = True, reset_criteria: bool = False) -> None:
    """Create tables and (optionally) seed default criteria if the table is empty."""
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)
        if reset_criteria:
            conn.execute("DELETE FROM evaluation_criteria")
        if seed:
            count = conn.execute("SELECT COUNT(*) FROM evaluation_criteria").fetchone()[0]
            if count == 0:
                conn.executemany(
                    """INSERT INTO evaluation_criteria
                       (criterion_id, name, description, weight, max_score, is_active)
                       VALUES (:criterion_id, :name, :description, :weight, :max_score, :is_active)""",
                    DEFAULT_CRITERIA,
                )


# ---------------------------------------------------------------- criteria
def get_all_criteria(db_path: str | None = None) -> list[dict[str, Any]]:
    with get_conn(db_path) as conn:
        rows = conn.execute("SELECT * FROM evaluation_criteria ORDER BY criterion_id").fetchall()
    return [dict(r) for r in rows]


def get_active_criteria(db_path: str | None = None) -> list[dict[str, Any]]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM evaluation_criteria WHERE is_active = 1 ORDER BY criterion_id"
        ).fetchall()
    return [dict(r) for r in rows]


def check_weights(criteria: list[dict[str, Any]]) -> tuple[bool, float]:
    """Return (is_valid, total) for the weights of the given (active) criteria."""
    total = round(sum(float(c["weight"]) for c in criteria), 4)
    return (len(criteria) > 0 and abs(total - 100.0) <= WEIGHT_TOLERANCE), total


def save_criteria(criteria: list[dict[str, Any]], db_path: str | None = None) -> None:
    """Upsert a full list of criteria (used by the Streamlit criteria editor)."""
    with get_conn(db_path) as conn:
        for c in criteria:
            conn.execute(
                """INSERT INTO evaluation_criteria (criterion_id, name, description, weight, max_score, is_active)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(criterion_id) DO UPDATE SET
                     name=excluded.name, description=excluded.description, weight=excluded.weight,
                     max_score=excluded.max_score, is_active=excluded.is_active""",
                (
                    int(c["criterion_id"]),
                    str(c["name"]).strip(),
                    str(c["description"]).strip(),
                    float(c["weight"]),
                    int(c["max_score"]),
                    1 if c["is_active"] else 0,
                ),
            )


# ---------------------------------------------------------------- runs
def create_run(rfp_run_id: str, created_at: str, supplier_count: int, provider: str, model: str,
               criteria: list[dict[str, Any]], db_path: str | None = None) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            """INSERT INTO rfp_runs (rfp_run_id, created_at, status, supplier_count, llm_provider, llm_model, criteria_snapshot)
               VALUES (?, ?, 'RUNNING', ?, ?, ?, ?)""",
            (rfp_run_id, created_at, supplier_count, provider, model, json.dumps(criteria)),
        )


def update_run_status(rfp_run_id: str, status: str, warnings: list[str] | None = None,
                      run_json: dict | None = None, db_path: str | None = None) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE rfp_runs SET status = ?, warnings = ?, run_json = ? WHERE rfp_run_id = ?",
            (status, json.dumps(warnings or []), json.dumps(run_json) if run_json else None, rfp_run_id),
        )


def save_supplier_results(rfp_run_id: str, suppliers: list[dict[str, Any]], db_path: str | None = None) -> None:
    """Persist every ranked supplier for one run in a single transaction."""
    with get_conn(db_path) as conn:
        conn.executemany(
            """INSERT INTO supplier_results
               (rfp_run_id, supplier_name, submission_date, experience_rating, absolute_score, ppi, final_rank, result_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    rfp_run_id,
                    s["supplier_name"],
                    s["submission_date"],
                    s["experience_rating"],
                    s["absolute_score"],
                    s["ppi"],
                    s["final_rank"],
                    json.dumps(s),
                )
                for s in suppliers
            ],
        )


def list_runs(db_path: str | None = None) -> list[dict[str, Any]]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """SELECT rfp_run_id, created_at, status, supplier_count, llm_provider, llm_model
               FROM rfp_runs ORDER BY created_at DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def get_run_json(rfp_run_id: str, db_path: str | None = None) -> dict | None:
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT run_json FROM rfp_runs WHERE rfp_run_id = ?", (rfp_run_id,)).fetchone()
    if row and row["run_json"]:
        return json.loads(row["run_json"])
    return None


def get_supplier_results(rfp_run_id: str, db_path: str | None = None) -> list[dict[str, Any]]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM supplier_results WHERE rfp_run_id = ? ORDER BY final_rank", (rfp_run_id,)
        ).fetchall()
    return [dict(r) for r in rows]
