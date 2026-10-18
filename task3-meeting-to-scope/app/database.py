"""SQLite persistence layer for Task 3 Meeting to Scope Agent."""

import json
import os
import sqlite3
from typing import Any
from app.schemas import (
    ApprovalAction,
    ApprovalResponse,
    ScopeDocument,
    ScopeDiffReport,
    ScopeStatus,
    TranscriptMetadata,
    TranscriptResponse,
)


class Database:
    """Thread-safe SQLite database manager for transcripts, scopes, and diffs."""

    def __init__(self, db_path: str = "storage/meeting_to_scope.db"):
        if not os.path.isabs(db_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, db_path)
        else:
            self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Transcripts table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS transcripts (
                    transcript_id TEXT PRIMARY KEY,
                    project_name TEXT,
                    client_name TEXT,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            # Scopes table (immutable versions)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS scopes (
                    scope_id TEXT PRIMARY KEY,
                    transcript_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    scope_json TEXT NOT NULL,
                    approved_by TEXT,
                    approved_at TEXT,
                    previous_version_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            # Scope Diffs table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS scope_diffs (
                    diff_id TEXT PRIMARY KEY,
                    base_scope_id TEXT NOT NULL,
                    diff_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            # Approval History audit log
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS approval_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    reviewer_name TEXT NOT NULL,
                    notes TEXT,
                    timestamp TEXT NOT NULL
                )
                """
            )
            conn.commit()

    # ==========================================
    # Transcripts
    # ==========================================
    def save_transcript(self, transcript: TranscriptResponse) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO transcripts 
                (transcript_id, project_name, client_name, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    transcript.transcript_id,
                    transcript.metadata.project_name,
                    transcript.metadata.client_name,
                    transcript.content,
                    transcript.metadata.model_dump_json(),
                    transcript.created_at,
                ),
            )
            conn.commit()

    def get_transcript(self, transcript_id: str) -> TranscriptResponse | None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM transcripts WHERE transcript_id = ?", (transcript_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            meta_dict = json.loads(row["metadata_json"])
            return TranscriptResponse(
                transcript_id=row["transcript_id"],
                content=row["content"],
                metadata=TranscriptMetadata(**meta_dict),
                char_count=len(row["content"]),
                created_at=row["created_at"],
            )

    # ==========================================
    # Scopes
    # ==========================================
    def save_scope(self, scope: ScopeDocument) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO scopes
                (scope_id, transcript_id, version, status, scope_json, approved_by, approved_at, previous_version_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scope.scope_id,
                    scope.transcript_id,
                    scope.version,
                    scope.status.value,
                    scope.model_dump_json(),
                    scope.approved_by,
                    scope.approved_at,
                    scope.previous_version_id,
                    scope.created_at,
                    scope.updated_at,
                ),
            )
            conn.commit()

    def get_scope(self, scope_id: str) -> ScopeDocument | None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scopes WHERE scope_id = ?", (scope_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return ScopeDocument.model_validate_json(row["scope_json"])

    def get_latest_approved_scope(self, project_name: str | None = None) -> ScopeDocument | None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if project_name:
                cursor.execute(
                    """
                    SELECT scope_json FROM scopes 
                    WHERE status = 'approved' AND scope_json LIKE ?
                    ORDER BY version DESC LIMIT 1
                    """,
                    (f'%"project_name":"{project_name}"%',),
                )
            else:
                cursor.execute(
                    """
                    SELECT scope_json FROM scopes 
                    WHERE status = 'approved'
                    ORDER BY version DESC LIMIT 1
                    """
                )
            row = cursor.fetchone()
            if not row:
                return None
            return ScopeDocument.model_validate_json(row["scope_json"])

    def list_scopes(self, limit: int = 50) -> list[ScopeDocument]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT scope_json FROM scopes ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
            return [ScopeDocument.model_validate_json(r["scope_json"]) for r in rows]

    # ==========================================
    # Scope Diffs
    # ==========================================
    def save_scope_diff(self, diff: ScopeDiffReport) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO scope_diffs (diff_id, base_scope_id, diff_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    diff.diff_id,
                    diff.base_scope_id,
                    diff.model_dump_json(),
                    diff.created_at,
                ),
            )
            conn.commit()

    def get_scope_diff(self, diff_id: str) -> ScopeDiffReport | None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM scope_diffs WHERE diff_id = ?", (diff_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return ScopeDiffReport.model_validate_json(row["diff_json"])

    # ==========================================
    # Approval History
    # ==========================================
    def log_approval_action(
        self,
        scope_id: str,
        version: int,
        action: ApprovalAction,
        reviewer_name: str,
        notes: str | None,
        timestamp: str,
    ) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO approval_history (scope_id, version, action, reviewer_name, notes, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    scope_id,
                    version,
                    action.value,
                    reviewer_name,
                    notes or "",
                    timestamp,
                ),
            )
            conn.commit()

    def get_approval_history(self, scope_id: str) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM approval_history WHERE scope_id = ? ORDER BY id ASC",
                (scope_id,),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
