"""SQLite database layer for articles, ingestion jobs, and escalations.

Isolates database operations to allow seamless future migration to PostgreSQL.
"""

from datetime import datetime, timezone
import json
import sqlite3
from typing import Any
from app.core.exceptions import StorageError
from app.core.logging import logger


class Database:
    """SQLite database manager for persistent metadata storage."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create and configure a SQLite connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency and foreign keys
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        """Create necessary database tables if they do not exist."""
        with self._get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,
                canonical_url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                headings_json TEXT DEFAULT '[]',
                images_json TEXT DEFAULT '[]',
                content_hash TEXT NOT NULL,
                published_at TEXT,
                modified_at TEXT,
                fetched_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                is_deleted INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS url_metadata (
                url TEXT PRIMARY KEY,
                last_modified_header TEXT,
                etag TEXT,
                last_crawled_at TEXT,
                http_status INTEGER,
                content_hash TEXT
            );

            CREATE TABLE IF NOT EXISTS ingestion_jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                urls_discovered INTEGER DEFAULT 0,
                articles_added INTEGER DEFAULT 0,
                articles_updated INTEGER DEFAULT 0,
                articles_unchanged INTEGER DEFAULT 0,
                articles_removed INTEGER DEFAULT 0,
                errors_json TEXT DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS ingestion_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(job_id, url)
            );

            CREATE TABLE IF NOT EXISTS escalations (
                escalation_id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                retrieved_evidence_json TEXT DEFAULT '[]',
                expert_answer TEXT,
                expert_name TEXT,
                answered_at TEXT,
                approved_by TEXT,
                approved_at TEXT,
                reindexed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                audit_trail_json TEXT DEFAULT '[]'
            );

            CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(canonical_url);
            CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
            CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalations(status);
            CREATE INDEX IF NOT EXISTS idx_ingestion_queue_job ON ingestion_queue(job_id, status);
            """)
        logger.info(f"Database initialized at {self.db_path}")

    # --- Article Operations ---

    def upsert_article(self, article: dict[str, Any]) -> dict[str, Any]:
        """Insert or update an article record."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_connection() as conn:
                existing = conn.execute(
                    "SELECT id, created_at FROM articles WHERE canonical_url = ?",
                    (article["canonical_url"],),
                ).fetchone()

                if existing:
                    article_id = existing["id"]
                    created_at = existing["created_at"]
                    conn.execute(
                        """
                        UPDATE articles SET
                            title = ?,
                            content = ?,
                            headings_json = ?,
                            images_json = ?,
                            content_hash = ?,
                            published_at = ?,
                            modified_at = ?,
                            fetched_at = ?,
                            status = ?,
                            is_deleted = ?,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            article["title"],
                            article["content"],
                            json.dumps(article.get("headings", [])),
                            json.dumps(
                                [
                                    img if isinstance(img, dict) else img.model_dump()
                                    for img in article.get("images", [])
                                ]
                            ),
                            article["content_hash"],
                            article.get("published_at"),
                            article.get("modified_at"),
                            str(article.get("fetched_at", now)),
                            article.get("status", "active"),
                            1 if article.get("is_deleted", False) else 0,
                            now,
                            article_id,
                        ),
                    )
                else:
                    import uuid

                    article_id = article.get("id") or str(uuid.uuid4())
                    created_at = now
                    conn.execute(
                        """
                        INSERT INTO articles (
                            id, canonical_url, title, content, headings_json,
                            images_json, content_hash, published_at, modified_at,
                            fetched_at, status, is_deleted, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            article_id,
                            article["canonical_url"],
                            article["title"],
                            article["content"],
                            json.dumps(article.get("headings", [])),
                            json.dumps(
                                [
                                    img if isinstance(img, dict) else img.model_dump()
                                    for img in article.get("images", [])
                                ]
                            ),
                            article["content_hash"],
                            article.get("published_at"),
                            article.get("modified_at"),
                            str(article.get("fetched_at", now)),
                            article.get("status", "active"),
                            1 if article.get("is_deleted", False) else 0,
                            created_at,
                            now,
                        ),
                    )

            return self.get_article(article_id)
        except Exception as e:
            raise StorageError(f"Failed to upsert article: {e}") from e

    def get_article(self, article_id: str) -> dict[str, Any] | None:
        """Fetch article by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM articles WHERE id = ?", (article_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_article(row)

    def get_article_by_url(self, canonical_url: str) -> dict[str, Any] | None:
        """Fetch article by canonical URL."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM articles WHERE canonical_url = ?", (canonical_url,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_article(row)

    def list_articles(
        self, limit: int = 50, offset: int = 0, include_deleted: bool = False
    ) -> tuple[list[dict[str, Any]], int]:
        """List articles with pagination."""
        with self._get_connection() as conn:
            where = "" if include_deleted else "WHERE is_deleted = 0"
            count = conn.execute(f"SELECT COUNT(*) FROM articles {where}").fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM articles {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [self._row_to_article(r) for r in rows], count

    def mark_article_deleted(self, article_id: str) -> bool:
        """Mark an article as deleted (soft delete)."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE articles SET is_deleted = 1, status = 'removed', updated_at = ? WHERE id = ?",
                (now, article_id),
            )
            return cursor.rowcount > 0

    def _row_to_article(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a database row into an article dictionary."""
        return {
            "id": row["id"],
            "canonical_url": row["canonical_url"],
            "title": row["title"],
            "content": row["content"],
            "headings": json.loads(row["headings_json"] or "[]"),
            "images": json.loads(row["images_json"] or "[]"),
            "content_hash": row["content_hash"],
            "published_at": row["published_at"],
            "modified_at": row["modified_at"],
            "fetched_at": row["fetched_at"],
            "status": row["status"],
            "is_deleted": bool(row["is_deleted"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # --- Ingestion Job Tracking ---

    def create_ingestion_job(self, job_id: str) -> None:
        """Record the start of a new ingestion job."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO ingestion_jobs (job_id, status, started_at)
                VALUES (?, 'running', ?)
                """,
                (job_id, now),
            )

    def update_ingestion_job(
        self,
        job_id: str,
        status: str,
        urls_discovered: int = 0,
        articles_added: int = 0,
        articles_updated: int = 0,
        articles_unchanged: int = 0,
        articles_removed: int = 0,
        errors: list[str] | None = None,
    ) -> None:
        """Update job metrics and completion status."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE ingestion_jobs SET
                    status = ?,
                    completed_at = ?,
                    urls_discovered = ?,
                    articles_added = ?,
                    articles_updated = ?,
                    articles_unchanged = ?,
                    articles_removed = ?,
                    errors_json = ?
                WHERE job_id = ?
                """,
                (
                    status,
                    now,
                    urls_discovered,
                    articles_added,
                    articles_updated,
                    articles_unchanged,
                    articles_removed,
                    json.dumps(errors or []),
                    job_id,
                ),
            )

    def get_latest_ingestion_job(self) -> dict[str, Any] | None:
        """Retrieve the most recent ingestion job."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM ingestion_jobs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            return {
                "job_id": row["job_id"],
                "status": row["status"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
                "urls_discovered": row["urls_discovered"],
                "articles_added": row["articles_added"],
                "articles_updated": row["articles_updated"],
                "articles_unchanged": row["articles_unchanged"],
                "articles_removed": row["articles_removed"],
                "errors": json.loads(row["errors_json"] or "[]"),
            }

    # --- Ingestion Queue & Crash Resumption Operations ---

    def init_ingestion_queue(self, job_id: str, urls: list[str]) -> int:
        """Initialize the persistent queue with URLs for a given job."""
        now = datetime.now(timezone.utc).isoformat()
        inserted = 0
        with self._get_connection() as conn:
            for url in urls:
                res = conn.execute(
                    """
                    INSERT OR IGNORE INTO ingestion_queue (job_id, url, status, created_at, updated_at)
                    VALUES (?, ?, 'pending', ?, ?)
                    """,
                    (job_id, url, now, now),
                )
                if res.rowcount > 0:
                    inserted += 1
        return inserted

    def get_pending_queue_urls(self, job_id: str, limit: int = 500) -> list[str]:
        """Fetch pending or retryable URLs for an ingestion job."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT url FROM ingestion_queue
                WHERE job_id = ? AND status IN ('pending', 'failed')
                ORDER BY id ASC LIMIT ?
                """,
                (job_id, limit),
            ).fetchall()
            return [r["url"] for r in rows]

    def update_queue_item(
        self, job_id: str, url: str, status: str, error_message: str | None = None
    ) -> None:
        """Update the status of an in-flight URL queue item."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE ingestion_queue SET
                    status = ?,
                    error_message = ?,
                    retry_count = retry_count + CASE WHEN ? = 'failed' THEN 1 ELSE 0 END,
                    updated_at = ?
                WHERE job_id = ? AND url = ?
                """,
                (status, error_message, status, now, job_id, url),
            )

    def get_queue_summary(self, job_id: str) -> dict[str, int]:
        """Return counts of queue items by status for a job."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM ingestion_queue WHERE job_id = ? GROUP BY status",
                (job_id,),
            ).fetchall()
            summary = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}
            for r in rows:
                summary[r["status"]] = r["cnt"]
            summary["total"] = sum(summary.values())
            return summary

    def get_resumable_job(self) -> dict[str, Any] | None:
        """Find the latest unfinished ingestion job that has pending queue items."""
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT j.* FROM ingestion_jobs j
                JOIN ingestion_queue q ON j.job_id = q.job_id
                WHERE q.status IN ('pending', 'failed') AND j.status IN ('running', 'failed', 'completed_with_errors')
                ORDER BY j.started_at DESC LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            return {
                "job_id": row["job_id"],
                "status": row["status"],
                "started_at": row["started_at"],
            }

    # --- Escalation Operations ---

    def create_escalation(
        self,
        escalation_id: str,
        question: str,
        retrieved_evidence: list[dict],
        context: dict | None = None,
    ) -> dict[str, Any]:
        """Create a new human escalation record."""
        now = datetime.now(timezone.utc).isoformat()
        audit_trail = [f"{now}: Escalation created due to insufficient evidence."]
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO escalations (
                    escalation_id, question, status, retrieved_evidence_json,
                    created_at, updated_at, audit_trail_json
                ) VALUES (?, ?, 'open', ?, ?, ?, ?)
                """,
                (
                    escalation_id,
                    question,
                    json.dumps(retrieved_evidence),
                    now,
                    now,
                    json.dumps(audit_trail),
                ),
            )
        return self.get_escalation(escalation_id)

    def get_escalation(self, escalation_id: str) -> dict[str, Any] | None:
        """Fetch escalation by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM escalations WHERE escalation_id = ?", (escalation_id,)
            ).fetchone()
            if not row:
                return None
            return {
                "escalation_id": row["escalation_id"],
                "question": row["question"],
                "status": row["status"],
                "retrieved_evidence": json.loads(row["retrieved_evidence_json"] or "[]"),
                "expert_answer": row["expert_answer"],
                "expert_name": row["expert_name"],
                "answered_at": row["answered_at"],
                "approved_by": row["approved_by"],
                "approved_at": row["approved_at"],
                "reindexed_at": row["reindexed_at"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "audit_trail": json.loads(row["audit_trail_json"] or "[]"),
            }

    def list_escalations(
        self, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        """List escalations with optional status filter."""
        with self._get_connection() as conn:
            if status:
                count = conn.execute(
                    "SELECT COUNT(*) FROM escalations WHERE status = ?", (status,)
                ).fetchone()[0]
                rows = conn.execute(
                    "SELECT * FROM escalations WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (status, limit, offset),
                ).fetchall()
            else:
                count = conn.execute("SELECT COUNT(*) FROM escalations").fetchone()[0]
                rows = conn.execute(
                    "SELECT * FROM escalations ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()

            return [
                {
                    "escalation_id": r["escalation_id"],
                    "question": r["question"],
                    "status": r["status"],
                    "retrieved_evidence": json.loads(
                        r["retrieved_evidence_json"] or "[]"
                    ),
                    "expert_answer": r["expert_answer"],
                    "expert_name": r["expert_name"],
                    "answered_at": r["answered_at"],
                    "approved_by": r["approved_by"],
                    "approved_at": r["approved_at"],
                    "reindexed_at": r["reindexed_at"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "audit_trail": json.loads(r["audit_trail_json"] or "[]"),
                }
                for r in rows
            ], count

    def answer_escalation(
        self, escalation_id: str, expert_answer: str, expert_name: str
    ) -> dict[str, Any]:
        """Provide a human expert answer to an open escalation."""
        now = datetime.now(timezone.utc).isoformat()
        current = self.get_escalation(escalation_id)
        if not current:
            raise StorageError(f"Escalation {escalation_id} not found.")

        audit_trail = current["audit_trail"]
        audit_trail.append(f"{now}: Answered by expert '{expert_name}'.")

        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE escalations SET
                    expert_answer = ?,
                    expert_name = ?,
                    status = 'answered',
                    answered_at = ?,
                    updated_at = ?,
                    audit_trail_json = ?
                WHERE escalation_id = ?
                """,
                (
                    expert_answer,
                    expert_name,
                    now,
                    now,
                    json.dumps(audit_trail),
                    escalation_id,
                ),
            )
        return self.get_escalation(escalation_id)

    def approve_escalation(
        self, escalation_id: str, approved_by: str, reviewer_notes: str | None = None
    ) -> dict[str, Any]:
        """Approve an answered escalation to mark it ready for knowledge indexing."""
        now = datetime.now(timezone.utc).isoformat()
        current = self.get_escalation(escalation_id)
        if not current:
            raise StorageError(f"Escalation {escalation_id} not found.")
        if current["status"] != "answered" and not current.get("expert_answer"):
            raise StorageError("Cannot approve escalation before an expert answer is provided.")

        audit_trail = current["audit_trail"]
        note = f" (Notes: {reviewer_notes})" if reviewer_notes else ""
        audit_trail.append(f"{now}: Approved by '{approved_by}'{note}.")

        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE escalations SET
                    status = 'approved',
                    approved_by = ?,
                    approved_at = ?,
                    updated_at = ?,
                    audit_trail_json = ?
                WHERE escalation_id = ?
                """,
                (
                    approved_by,
                    now,
                    now,
                    json.dumps(audit_trail),
                    escalation_id,
                ),
            )
        return self.get_escalation(escalation_id)

    def mark_escalation_reindexed(self, escalation_id: str) -> None:
        """Mark that the approved escalation has been indexed into the vector store."""
        now = datetime.now(timezone.utc).isoformat()
        current = self.get_escalation(escalation_id)
        if not current:
            return

        audit_trail = current["audit_trail"]
        audit_trail.append(f"{now}: Indexed into vector knowledge base.")

        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE escalations SET
                    reindexed_at = ?,
                    updated_at = ?,
                    audit_trail_json = ?
                WHERE escalation_id = ?
                """,
                (
                    now,
                    now,
                    json.dumps(audit_trail),
                    escalation_id,
                ),
            )
