"""Unit tests for SQLite database layer."""

import tempfile
import pytest
from app.services.database import Database


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for isolated test execution."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db = Database(tmp.name)
        yield db


def test_article_lifecycle(temp_db):
    """Test upserting, retrieving, listing, and soft-deleting an article."""
    article_data = {
        "canonical_url": "https://support.brilliantdirectories.com/article/1",
        "title": "Getting Started",
        "content": "This is a guide to getting started with Brilliant Directories.",
        "headings": ["Introduction", "Quick Setup"],
        "images": [{"url": "https://example.com/setup.png", "alt_text": "Setup diagram"}],
        "content_hash": "hash_12345",
        "status": "active",
        "is_deleted": False,
    }

    # Upsert new article
    saved = temp_db.upsert_article(article_data)
    assert saved["id"] is not None
    assert saved["title"] == "Getting Started"
    assert len(saved["headings"]) == 2
    assert len(saved["images"]) == 1

    # Fetch by ID and URL
    by_id = temp_db.get_article(saved["id"])
    assert by_id["title"] == "Getting Started"
    by_url = temp_db.get_article_by_url(article_data["canonical_url"])
    assert by_url["id"] == saved["id"]

    # List articles
    articles, total = temp_db.list_articles()
    assert total == 1
    assert articles[0]["id"] == saved["id"]

    # Update article
    article_data["title"] = "Getting Started - Updated"
    article_data["content_hash"] = "hash_updated"
    updated = temp_db.upsert_article(article_data)
    assert updated["id"] == saved["id"]
    assert updated["title"] == "Getting Started - Updated"

    # Soft delete
    deleted = temp_db.mark_article_deleted(saved["id"])
    assert deleted is True

    # After soft delete, list_articles without include_deleted excludes it
    active_articles, active_total = temp_db.list_articles(include_deleted=False)
    assert active_total == 0

    all_articles, all_total = temp_db.list_articles(include_deleted=True)
    assert all_total == 1
    assert all_articles[0]["is_deleted"] is True


def test_escalation_lifecycle(temp_db):
    """Test human escalation creation, answering, and approval workflow."""
    evidence = [{"article_title": "Setup", "url": "https://example.com", "excerpt": "Some text"}]
    esc = temp_db.create_escalation(
        escalation_id="esc-001",
        question="How do I configure custom SSL?",
        retrieved_evidence=evidence,
    )
    assert esc["escalation_id"] == "esc-001"
    assert esc["status"] == "open"

    # Human expert answers
    answered = temp_db.answer_escalation(
        escalation_id="esc-001",
        expert_answer="Custom SSL is configured under Settings > Domain.",
        expert_name="Support Engineer Alice",
    )
    assert answered["status"] == "answered"
    assert answered["expert_answer"] == "Custom SSL is configured under Settings > Domain."

    # Knowledge admin approves
    approved = temp_db.approve_escalation(
        escalation_id="esc-001",
        approved_by="Admin Bob",
        reviewer_notes="Verified with documentation.",
    )
    assert approved["status"] == "approved"
    assert approved["approved_by"] == "Admin Bob"
    assert len(approved["audit_trail"]) == 3
