from __future__ import annotations
"""
IssueLens Database Setup

Uses SQLite via aiosqlite for async operations.
Stores analysis history as JSON for simplicity.
"""

import aiosqlite
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Database file path — stored alongside the backend
DB_PATH = Path(__file__).parent.parent / "issueLens.db"


async def init_database() -> None:
    """Create the database tables if they don't exist.
    
    Called once at application startup.
    """
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                github_url TEXT NOT NULL,
                repo_owner TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                issue_number INTEGER NOT NULL,
                issue_type TEXT NOT NULL,
                issue_title TEXT NOT NULL DEFAULT '',
                overall_assessment TEXT,
                overall_confidence REAL,
                report_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.commit()
    logger.info("Database initialized at %s", DB_PATH)


async def _ensure_initialized() -> None:
    """Ensure database tables exist."""
    await init_database()


async def save_analysis(analysis_id: str, data: dict[str, Any]) -> None:
    """Save a completed analysis to the database."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO analyses 
            (id, github_url, repo_owner, repo_name, issue_number, issue_type,
             issue_title, overall_assessment, overall_confidence, report_json,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis_id,
                data.get("github_url", ""),
                data.get("repo_owner", ""),
                data.get("repo_name", ""),
                data.get("issue_number", 0),
                data.get("issue_type", "issue"),
                data.get("issue_title", ""),
                data.get("overall_assessment"),
                data.get("overall_confidence"),
                json.dumps(data.get("report", {})),
                data.get("created_at", now),
                now,
            ),
        )
        await db.commit()


async def get_analysis(analysis_id: str) -> dict[str, Any] | None:
    """Retrieve a single analysis by ID."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM analyses WHERE id = ?", (analysis_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_dict(row)


async def get_history(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """Retrieve analysis history, most recent first."""
    await _ensure_initialized()
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM analyses ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(row) for row in rows]


async def get_stats() -> dict[str, int]:
    """Get summary statistics for the dashboard."""
    await _ensure_initialized()
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM analyses")
        total = (await cursor.fetchone())[0]
        
        cursor = await db.execute(
            "SELECT COUNT(*) FROM analyses WHERE overall_assessment = 'CONFIRMED'"
        )
        confirmed = (await cursor.fetchone())[0]
        
        cursor = await db.execute(
            "SELECT COUNT(*) FROM analyses WHERE overall_assessment = 'INVALID'"
        )
        invalid = (await cursor.fetchone())[0]
        
        cursor = await db.execute(
            "SELECT COUNT(*) FROM analyses WHERE overall_assessment = 'CANNOT_REPRODUCE'"
        )
        cannot_reproduce = (await cursor.fetchone())[0]
        
        return {
            "total": total,
            "confirmed": confirmed,
            "invalid": invalid,
            "cannot_reproduce": cannot_reproduce,
        }


def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
    """Convert a database row to a dictionary, parsing the JSON report."""
    result = dict(row)
    if "report_json" in result and result["report_json"]:
        try:
            result["report"] = json.loads(result["report_json"])
        except json.JSONDecodeError:
            result["report"] = {}
    return result
