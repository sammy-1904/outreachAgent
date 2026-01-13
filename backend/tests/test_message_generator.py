"""Unit tests for message generation module."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models import Base, Lead, LeadStatus, Message
from backend.lead_generator import generate_leads
from backend.enricher import enrich_leads
from backend.message_generator import (
    generate_messages, 
    _truncate_to_word_limit,
    EMAIL_MAX_WORDS,
    DM_MAX_WORDS,
)


@pytest.fixture
def test_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def session_with_enriched_leads(test_session):
    """Create session with enriched leads ready for messaging."""
    generate_leads(test_session, count=5, seed=42)
    enrich_leads(test_session, ai_mode=False)
    return test_session


class TestMessageGenerator:
    """Tests for message generation functionality."""
    
    def test_generate_messages_creates_ab_variants(self, session_with_enriched_leads):
        """Test that A/B variants are created for each lead."""
        messages = generate_messages(session_with_enriched_leads)
        
        assert len(messages) == 5
        for msg in messages:
            assert msg.email_a is not None
            assert msg.email_b is not None
            assert msg.dm_a is not None
            assert msg.dm_b is not None
            assert msg.cta is not None
    
    def test_variants_are_different(self, session_with_enriched_leads):
        """Test that A and B variants are meaningfully different."""
        messages = generate_messages(session_with_enriched_leads)
        
        for msg in messages:
            # Email variants should be different (different focus)
            assert msg.email_a != msg.email_b
            
            # DM variants should be different
            assert msg.dm_a != msg.dm_b
    
    def test_messages_reference_enriched_data(self, session_with_enriched_leads):
        """Test that messages include enriched insights."""
        messages = generate_messages(session_with_enriched_leads)
        
        for msg in messages:
            lead = session_with_enriched_leads.query(Lead).get(msg.lead_id)
            
            # Check email A references pain points
            if lead.pains:
                first_pain = lead.pains.split(";")[0].strip()
                # Pain should appear in variant A (pain-focused)
                assert first_pain.lower() in msg.email_a.lower() or "challenge" in msg.email_a.lower()
            
            # Check email B references triggers
            if lead.triggers:
                first_trigger = lead.triggers.split(";")[0].strip()
                assert first_trigger.lower() in msg.email_b.lower() or lead.industry.lower() in msg.email_b.lower()
    
    def test_email_word_limit_enforced(self, session_with_enriched_leads):
        """Test emails stay within 120 word limit."""
        messages = generate_messages(session_with_enriched_leads)
        
        for msg in messages:
            email_a_words = len(msg.email_a.split())
            email_b_words = len(msg.email_b.split())
            
            assert email_a_words <= EMAIL_MAX_WORDS + 5  # Small tolerance
            assert email_b_words <= EMAIL_MAX_WORDS + 5
    
    def test_dm_word_limit_enforced(self, session_with_enriched_leads):
        """Test DMs stay within 60 word limit."""
        messages = generate_messages(session_with_enriched_leads)
        
        for msg in messages:
            dm_a_words = len(msg.dm_a.split())
            dm_b_words = len(msg.dm_b.split())
            
            assert dm_a_words <= DM_MAX_WORDS + 5  # Small tolerance
            assert dm_b_words <= DM_MAX_WORDS + 5
    
    def test_cta_included(self, session_with_enriched_leads):
        """Test CTA is present in messages."""
        messages = generate_messages(session_with_enriched_leads)
        
        for msg in messages:
            assert "15-minute call" in msg.email_a or "call" in msg.email_a.lower()
            assert "call" in msg.dm_a.lower()
    
    def test_lead_status_updated(self, session_with_enriched_leads):
        """Test leads are marked as MESSAGED after generation."""
        generate_messages(session_with_enriched_leads)
        
        leads = session_with_enriched_leads.query(Lead).all()
        for lead in leads:
            assert lead.status == LeadStatus.MESSAGED


class TestWordTruncation:
    """Tests for word limit truncation function."""
    
    def test_short_text_unchanged(self):
        """Test text under limit is not modified."""
        text = "This is a short message."
        result = _truncate_to_word_limit(text, 100)
        assert result == text
    
    def test_long_text_truncated(self):
        """Test text over limit is truncated."""
        text = " ".join(["word"] * 150)
        result = _truncate_to_word_limit(text, 50)
        
        word_count = len(result.split())
        assert word_count <= 51  # 50 words + possible trailing punctuation
    
    def test_truncation_adds_ellipsis(self):
        """Test truncated text ends with ellipsis if no punctuation."""
        text = "word " * 100
        result = _truncate_to_word_limit(text, 10)
        
        assert result.endswith("...")
