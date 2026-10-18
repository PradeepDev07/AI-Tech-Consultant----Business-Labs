"""Transcript ingestion and validation service."""

import uuid
from datetime import datetime, timezone
from app.database import Database
from app.schemas import TranscriptCreate, TranscriptResponse


class TranscriptService:
    """Validates and stores meeting transcripts."""

    def __init__(self, database: Database, max_length: int = 50000):
        self.database = database
        self.max_length = max_length

    def ingest_transcript(self, payload: TranscriptCreate) -> TranscriptResponse:
        """Validates and assigns a stable transcript ID, then persists to SQLite."""
        text = payload.transcript_text.strip()
        if len(text) < 10:
            raise ValueError("Transcript content must contain at least 10 characters.")
        if len(text) > self.max_length:
            raise ValueError(
                f"Transcript exceeds maximum allowed length of {self.max_length} characters (received {len(text)})."
            )

        transcript_id = f"tr_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()

        response = TranscriptResponse(
            transcript_id=transcript_id,
            content=text,
            metadata=payload.metadata,
            char_count=len(text),
            created_at=now,
        )

        self.database.save_transcript(response)
        return response

    def get_transcript(self, transcript_id: str) -> TranscriptResponse | None:
        """Retrieves a previously stored transcript by ID."""
        return self.database.get_transcript(transcript_id)
