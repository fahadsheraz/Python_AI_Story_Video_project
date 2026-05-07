from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "app.db"
COLAB_JOBS_DIR = DATA_DIR / "colab_jobs"


def init_db() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                story TEXT NOT NULL,
                segmentation_json TEXT NOT NULL,
                locked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def create_project(title: str, story: str, segmentation: dict) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO projects (title, story, segmentation_json, locked)
            VALUES (?, ?, ?, ?)
            """,
            (title, story, json.dumps(segmentation, ensure_ascii=False), 0),
        )
        return int(cursor.lastrowid)


def get_project(project_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, title, story, segmentation_json, locked
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row["id"],
        "title": row["title"],
        "story": row["story"],
        "segmentation": json.loads(row["segmentation_json"]),
        "locked": bool(row["locked"]),
    }


def update_segmentation(project_id: int, segmentation: dict, locked: bool = False) -> bool:
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE projects
            SET segmentation_json = ?, locked = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (json.dumps(segmentation, ensure_ascii=False), int(locked), project_id),
        )
        return cursor.rowcount > 0


def list_projects() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, title, story, segmentation_json, locked
            FROM projects
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()

    return [
        {
            "id": row["id"],
            "title": row["title"],
            "story": row["story"],
            "segmentation": json.loads(row["segmentation_json"]),
            "locked": bool(row["locked"]),
        }
        for row in rows
    ]


def create_colab_job(project_id: int) -> dict | None:
    project = get_project(project_id)
    if project is None:
        return None

    job_id = f"job_{project_id:04d}"
    job_dir = COLAB_JOBS_DIR / job_id
    input_dir = job_dir / "input"
    output_dir = job_dir / "output"

    input_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "characters").mkdir(parents=True, exist_ok=True)
    (output_dir / "backgrounds").mkdir(parents=True, exist_ok=True)
    (output_dir / "audio").mkdir(parents=True, exist_ok=True)
    (output_dir / "video").mkdir(parents=True, exist_ok=True)

    segmentation_path = input_dir / "segmentation.json"
    status_path = job_dir / "status.json"

    segmentation_path.write_text(
        json.dumps(project["segmentation"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    status = {
        "job_id": job_id,
        "project_id": project_id,
        "status": "ready_for_colab",
        "step": "waiting_for_character_generation",
        "progress": 0,
    }
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "job_id": job_id,
        "job_path": str(job_dir.resolve()),
        "segmentation_path": str(segmentation_path.resolve()),
        "status_path": str(status_path.resolve()),
        "status": status,
    }


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
