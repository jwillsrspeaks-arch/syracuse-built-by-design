"""BUILT BY DESIGN — assessment capture API.

Saves participant sessions in real time (one write per navigation step) and
serves aggregated results for the live dashboard.
"""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

DB_PATH = Path(os.environ.get("BBD_DB_PATH", "/data/assessment.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

PILLAR_KEYS = [
    "intention", "structure", "standards", "execution",
    "stewardship", "adaptability", "succession",
]

# 10 questions x 5-point Likert per pillar, weighted x1.4 -> 70/pillar, 490 total
WEIGHT = 1.4

CLASSIFICATION_RULES = [
    (364, 490, "Built by Design"),
    (238, 363, "Under Construction"),
    (0, 237, "Built by Default"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    org_name TEXT NOT NULL DEFAULT '',
    audience_type TEXT NOT NULL DEFAULT '',
    lens TEXT NOT NULL DEFAULT 'auto',
    team TEXT NOT NULL DEFAULT '',
    respondent TEXT NOT NULL DEFAULT '{}',
    answers TEXT NOT NULL DEFAULT '{}',
    cursor TEXT NOT NULL DEFAULT '{"p":0,"q":0}',
    answered_count INTEGER NOT NULL DEFAULT 0,
    pillar_scores TEXT NOT NULL DEFAULT '{}',
    total_score INTEGER NOT NULL DEFAULT 0,
    classification TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


with db() as _c:
    _c.executescript(SCHEMA)


def classification(total: int) -> str:
    for lo, hi, label in CLASSIFICATION_RULES:
        if lo <= total <= hi:
            return label
    return "Built by Default"


def score_answers(answers: Dict[str, Any]):
    """Pillar sums (max 70 each, weighted x1.4), total (max 490), answered count."""
    pillar_scores = {}
    answered = 0
    for key in PILLAR_KEYS:
        values = [v for v in (answers.get(key) or []) if isinstance(v, (int, float))]
        pillar_scores[key] = round(sum(values) * WEIGHT)
        answered += len(values)
    total = int(sum(pillar_scores.values()))
    return pillar_scores, total, answered, classification(total)


def row_to_state(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "orgName": row["org_name"],
        "audienceType": row["audience_type"],
        "lensOverride": row["lens"],
        "team": row["team"],
        "respondent": json.loads(row["respondent"]),
        "answers": json.loads(row["answers"]),
        "cursor": json.loads(row["cursor"]),
        "answeredCount": row["answered_count"],
        "pillarScores": json.loads(row["pillar_scores"]),
        "totalScore": row["total_score"],
        "classification": row["classification"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "completedAt": row["completed_at"],
    }


class SessionCreate(BaseModel):
    orgName: str = ""
    audienceType: str = ""
    lensOverride: str = "auto"
    team: str = ""
    respondent: Dict[str, Any] = {}


class SessionSave(BaseModel):
    orgName: str = ""
    audienceType: str = ""
    lensOverride: str = "auto"
    team: str = ""
    respondent: Dict[str, Any] = {}
    answers: Dict[str, Any] = {}
    cursor: Dict[str, Any] = {"p": 0, "q": 0}
    completed: bool = False


app = FastAPI(title="BBD Assessment API")


@app.get("/api/healthz")
def healthz():
    with db() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()["n"]
    return {"ok": True, "sessions": count}


@app.post("/api/session")
def create_session(payload: SessionCreate):
    sid = "s_" + uuid.uuid4().hex[:20]
    ts = now_iso()
    with db() as conn:
        conn.execute(
            """INSERT INTO sessions
               (id, org_name, audience_type, lens, team, respondent, answers, cursor,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (sid, payload.orgName, payload.audienceType, payload.lensOverride,
             payload.team, json.dumps(payload.respondent),
             json.dumps({}), json.dumps({"p": 0, "q": 0}), ts, ts),
        )
    return {"id": sid, "savedAt": ts}


@app.put("/api/session/{sid}")
def save_session(sid: str, payload: SessionSave):
    ts = now_iso()
    pillar_scores, total, answered, cls = score_answers(payload.answers)
    with db() as conn:
        cur = conn.execute("SELECT id FROM sessions WHERE id=?", (sid,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Session not found")
        completed_at = ts if payload.completed else None
        conn.execute(
            """UPDATE sessions SET
                 org_name=?, audience_type=?, lens=?, team=?, respondent=?,
                 answers=?, cursor=?, answered_count=?, pillar_scores=?,
                 total_score=?, classification=?, updated_at=?,
                 completed_at=COALESCE(?, completed_at)
               WHERE id=?""",
            (payload.orgName, payload.audienceType, payload.lensOverride,
             payload.team, json.dumps(payload.respondent), json.dumps(payload.answers),
             json.dumps(payload.cursor), answered, json.dumps(pillar_scores),
             total, cls, ts, completed_at, sid),
        )
    return {"ok": True, "answered": answered, "total": total,
            "classification": cls, "savedAt": ts}


@app.get("/api/session/{sid}")
def get_session(sid: str):
    with db() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return row_to_state(row)


def require_dashboard_key(x_dashboard_key: Optional[str]):
    expected = os.environ.get("DASHBOARD_PASSWORD", "")
    if not expected:
        raise HTTPException(status_code=503,
                            detail="Dashboard is locked: set the DASHBOARD_PASSWORD secret.")
    if x_dashboard_key != expected:
        raise HTTPException(status_code=401, detail="Invalid dashboard key.")


@app.get("/api/dashboard")
def dashboard(x_dashboard_key: Optional[str] = Header(default=None)):
    require_dashboard_key(x_dashboard_key)

    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC"
        ).fetchall()

    participants = []
    for row in rows:
        respondent = json.loads(row["respondent"])
        participants.append({
            "name": respondent.get("name") or "(unnamed)",
            "role": respondent.get("role") or "",
            "title": respondent.get("title") or "",
            "unit": respondent.get("unit") or "",
            "team": row["team"],
            "org": row["org_name"],
            "lens": row["lens"],
            "answered": row["answered_count"],
            "totalQuestions": 70,
            "pillarScores": json.loads(row["pillar_scores"]),
            "total": row["total_score"],
            "classification": row["classification"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "completedAt": row["completed_at"],
        })

    # Group by team; individuals without a team become their own entity.
    teams: Dict[str, list] = {}
    for p in participants:
        team_name = p["team"].strip() or f"Individual — {p['name']}"
        teams.setdefault(team_name, []).append(p)

    team_payload = []
    for team_name, members in sorted(teams.items()):
        avg_pillars = {}
        for key in PILLAR_KEYS:
            avg_pillars[key] = round(
                sum(m["pillarScores"].get(key, 0) for m in members) / len(members), 1
            )
        cls_counts = {}
        for m in members:
            if m["classification"]:
                cls_counts[m["classification"]] = cls_counts.get(m["classification"], 0) + 1
        team_payload.append({
            "team": team_name,
            "participantCount": len(members),
            "avgTotal": round(
                sum(m["total"] for m in members) / len(members), 1
            ),
            "avgPillars": avg_pillars,
            "classificationCounts": cls_counts,
            "participants": members,
        })

    completed = sum(1 for p in participants if p["completedAt"])
    return {
        "generatedAt": now_iso(),
        "summary": {
            "participants": len(participants),
            "completed": completed,
            "inProgress": len(participants) - completed,
            "teams": len(team_payload),
        },
        "teams": team_payload,
    }
