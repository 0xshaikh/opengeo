"""Small SQLite store for visibility history / trend tracking."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional


def _connect(db_path: str) -> sqlite3.Connection:
    parent = os.path.dirname(os.path.abspath(db_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT NOT NULL,
            brand_domain TEXT NOT NULL,
            query_count INTEGER NOT NULL,
            score       REAL,
            label       TEXT,
            payload     TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_runs_domain ON runs(brand_domain, ts);
        """
    )
    conn.commit()
    return conn


def _esc(value: str) -> str:
    return str(value).replace("'", "''")


def save_snapshot(db_path: str, payload: dict) -> int:
    """Persist a `check_visibility` result. Returns the inserted run_id."""
    conn = _connect(db_path)
    try:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        score = payload.get("score") or {}
        cur = conn.execute(
            "INSERT INTO runs (ts, brand_domain, query_count, score, label, payload) "
            "VALUES (?,?,?,?,?,?)",
            (
                ts,
                payload.get("brand_domain") or "unknown",
                len(payload.get("queries") or []),
                score.get("score"),
                score.get("label"),
                json.dumps(payload),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def load_runs(db_path: str, domain: Optional[str] = None, limit: int = 50) -> list[dict]:
    """Return runs, newest first, with the full payload decoded."""
    conn = _connect(db_path)
    try:
        if domain:
            rows = conn.execute(
                "SELECT run_id, ts, brand_domain, query_count, score, label, payload "
                "FROM runs WHERE brand_domain = ? ORDER BY run_id DESC LIMIT ?",
                (_esc(domain), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT run_id, ts, brand_domain, query_count, score, label, payload "
                "FROM runs ORDER BY run_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            try:
                d["payload"] = json.loads(row["payload"])
            except Exception:
                d["payload"] = None
            out.append(d)
        return out
    finally:
        conn.close()


def trend_rows(db_path: str, domain: Optional[str] = None, limit: int = 200) -> list[dict]:
    """Flat rows: one per (run, query, engine) so trends are easy to diff."""
    runs = load_runs(db_path, domain=domain, limit=limit)
    rows: list[dict] = []
    for run in runs:
        payload = run.get("payload") or {}
        for result in payload.get("results") or []:
            rows.append({
                "run_id": run.get("run_id"),
                "ts": run.get("ts"),
                "brand_domain": run.get("brand_domain"),
                "query": result.get("query"),
                "engine": result.get("engine"),
                "coverage": result.get("coverage"),
                "mentioned_in_answer": result.get("mentioned_in_answer"),
                "mentioned_in_organic": result.get("mentioned_in_organic"),
                "brand_rank": result.get("brand_rank"),
                "score": run.get("score"),
                "label": run.get("label"),
            })
    return rows


def list_domains(db_path: str) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT brand_domain, COUNT(*) AS runs, MAX(ts) AS latest, "
            "MAX(score) AS last_score "
            "FROM runs GROUP BY brand_domain ORDER BY latest DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
