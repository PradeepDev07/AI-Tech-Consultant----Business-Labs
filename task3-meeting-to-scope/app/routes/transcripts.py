"""Transcript ingestion and retrieval endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from app.dependencies import get_transcript_service
from app.schemas import TranscriptCreate, TranscriptResponse
from app.services.transcript_service import TranscriptService

router = APIRouter(prefix="/api/v1/transcripts", tags=["transcripts"])


@router.post("", response_model=TranscriptResponse, status_code=status.HTTP_201_CREATED)
def submit_transcript(
    payload: TranscriptCreate,
    service: TranscriptService = Depends(get_transcript_service),
):
    """Ingest and validate a raw meeting transcript."""
    try:
        return service.ingest_transcript(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{transcript_id}", response_model=TranscriptResponse)
def get_transcript(
    transcript_id: str,
    service: TranscriptService = Depends(get_transcript_service),
):
    """Retrieve a previously ingested transcript by ID."""
    transcript = service.get_transcript(transcript_id)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript not found: {transcript_id}",
        )
    return transcript
