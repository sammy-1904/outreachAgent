"""Unit tests for lead enrichment module."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models import Base, Lead, LeadStatus
from backend.lead_generator import generate_leads
from backend.enricher import enrich_leads, _apply_heuristics, _persona_from_title, _safe_sample


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
def session_with_leads(test_session):
    """Create session with pre-generated leads."""
    generate_leads(test_session, count=10, seed=42)
    return test_session


class TestEnricher:
    """Tests for lead enrichment functionality."""
    
    def test_enrich_leads_offline_mode(self, session_with_leads):
        """Test offline enrichment adds required fields."""
        leads = enrich_leads(session_with_leads, ai_mode=False)
        
        assert len(leads) == 10
        for lead in leads:
            assert lead.status == LeadStatus.ENRICHED
            assert lead.company_size is not None
            assert lead.persona is not None
            assert lead.pains is not None
            assert lead.triggers is not None
            assert lead.confidence is not None
            assert 55 <= lead.confidence <= 98
    
    def test_enrich_leads_with_limit(self, session_with_leads):
        """Test enrichment respects limit parameter."""
        leads = enrich_leads(session_with_leads, ai_mode=False, limit=5)
        assert len(leads) == 5
        
        # Check remaining leads are still NEW
        new_leads = session_with_leads.query(Lead).filter(
            Lead.status == LeadStatus.NEW
        ).count()
        assert new_leads == 5
    
    def test_persona_from_title(self):
        """Test persona extraction from job titles."""
        assert _persona_from_title("VP Engineering") == "Executive"
        assert _persona_from_title("Head of Product") == "Department Head"
        assert _persona_from_title("Director of Sales") == "Director"
        assert _persona_from_title("Engineering Manager") == "Manager"
        assert _persona_from_title("Tech Lead") == "Lead"
        assert _persona_from_title("CTO") == "C-Suite"
        assert _persona_from_title("Software Engineer") == "Professional"
    
    def test_safe_sample_handles_small_lists(self):
        """Test safe_sample doesn't crash on small lists."""
        result = _safe_sample(["one"], 3)
        assert len(result) == 1
        
        result = _safe_sample([], 2)
        assert len(result) == 0
        
        result = _safe_sample(["a", "b", "c"], 2)
        assert len(result) == 2
    
    def test_heuristics_apply_correctly(self, test_session):
        """Test heuristic enrichment applies correct values."""
        lead = Lead(
            full_name="Test User",
            company="Test Corp",
            title="VP Operations",
            industry="Manufacturing",
            website="https://test.com",
            email="test@test.com",
            linkedin="https://linkedin.com/in/test",
            country="US",
            status=LeadStatus.NEW,
        )
        test_session.add(lead)
        test_session.commit()
        
        _apply_heuristics(lead)
        
        assert lead.company_size == "Enterprise"  # Manufacturing default
        assert lead.persona == "Executive"  # VP maps to Executive
        assert ";" in lead.pains or len(lead.pains) > 0
        assert lead.triggers is not None
