"""Unit tests for message sending module."""
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models import Base, Lead, LeadStatus, Message
from backend.lead_generator import generate_leads
from backend.enricher import enrich_leads
from backend.message_generator import generate_messages
from backend.sender import send_messages, RateLimiter


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
def session_with_messages(test_session):
    """Create session with leads ready to send."""
    generate_leads(test_session, count=5, seed=42)
    enrich_leads(test_session, ai_mode=False)
    generate_messages(test_session)
    return test_session


class TestSender:
    """Tests for message sending functionality."""
    
    def test_dry_run_mode(self, session_with_messages):
        """Test dry run doesn't actually send emails."""
        with patch('backend.sender._send_email_smtp') as mock_smtp:
            sent = send_messages(session_with_messages, dry_run=True)
            
            assert len(sent) == 5
            mock_smtp.assert_not_called()
            
            # All leads should be SENT status
            for lead in sent:
                assert lead.status == LeadStatus.SENT
    
    def test_retry_logic(self, session_with_messages):
        """Test retry mechanism on failure."""
        with patch('backend.sender._send_email_smtp') as mock_smtp:
            # Fail twice, then succeed
            mock_smtp.side_effect = [
                Exception("Connection error"),
                Exception("Timeout"),
                None  # Success on 3rd try
            ] * 5  # For all 5 leads
            
            with patch('backend.sender.time.sleep'):  # Skip actual sleep
                sent = send_messages(
                    session_with_messages, 
                    dry_run=False, 
                    max_retries=2
                )
            
            # Should eventually succeed for all
            assert len(sent) == 5
    
    def test_max_retries_exceeded(self, test_session):
        """Test leads marked FAILED after max retries."""
        # Create a single lead
        lead = Lead(
            full_name="Test User",
            company="Test Corp",
            title="Manager",
            industry="Software",
            website="https://test.com",
            email="test@test.com",
            linkedin="https://linkedin.com/in/test",
            country="US",
            status=LeadStatus.MESSAGED,
        )
        test_session.add(lead)
        test_session.commit()
        
        msg = Message(
            lead_id=lead.id,
            email_a="Test email",
            dm_a="Test DM",
        )
        test_session.add(msg)
        test_session.commit()
        
        with patch('backend.sender._send_email_smtp') as mock_smtp:
            mock_smtp.side_effect = Exception("Always fail")
            
            with patch('backend.sender.time.sleep'):
                sent = send_messages(
                    test_session, 
                    dry_run=False, 
                    max_retries=2
                )
            
            assert len(sent) == 0
            assert lead.status == LeadStatus.FAILED
            assert lead.last_error is not None


class TestRateLimiter:
    """Tests for rate limiting functionality."""
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter calculates correct interval."""
        limiter = RateLimiter(60)  # 60 per minute = 1 per second
        assert limiter.interval == 1.0
        
        limiter = RateLimiter(10)  # 10 per minute = 6 second intervals
        assert limiter.interval == 6.0
    
    def test_rate_limiter_zero_rate(self):
        """Test rate limiter handles zero rate gracefully."""
        limiter = RateLimiter(0)
        limiter.wait_if_needed()  # Should not raise
    
    def test_rate_limiter_waits_appropriately(self):
        """Test rate limiter actually waits when needed."""
        import time
        
        limiter = RateLimiter(600)  # 0.1 second intervals
        
        # First call should not wait
        start = time.time()
        limiter.wait_if_needed()
        first_duration = time.time() - start
        
        # Second call immediately after should wait
        start = time.time()
        limiter.wait_if_needed()
        second_duration = time.time() - start
        
        # First should be fast, second should be ~0.1s
        assert first_duration < 0.05
        assert second_duration >= 0.05  # At least some waiting
