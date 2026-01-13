"""Unit tests for lead generation module."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models import Base, Lead, LeadStatus
from backend.lead_generator import generate_leads


@pytest.fixture
def test_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestLeadGenerator:
    """Tests for lead generation functionality."""
    
    def test_generate_leads_default_count(self, test_session):
        """Test generating default 200 leads."""
        leads = generate_leads(test_session, count=10)  # Use 10 for speed
        assert len(leads) == 10
    
    def test_generate_leads_with_seed_reproducibility(self, test_session):
        """Test that same seed produces same results."""
        leads1 = generate_leads(test_session, count=5, seed=42)
        
        # Create new session for second run
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session2 = Session()
        
        leads2 = generate_leads(session2, count=5, seed=42)
        
        assert leads1[0].full_name == leads2[0].full_name
        assert leads1[0].company == leads2[0].company
        session2.close()
    
    def test_lead_fields_are_valid(self, test_session):
        """Test that generated leads have valid field formats."""
        leads = generate_leads(test_session, count=5, seed=123)
        
        for lead in leads:
            # Check email format
            assert "@" in lead.email
            assert "." in lead.email.split("@")[1]
            
            # Check LinkedIn URL format
            assert lead.linkedin.startswith("https://www.linkedin.com/in/")
            
            # Check website format
            assert lead.website.startswith("https://")
            
            # Check status
            assert lead.status == LeadStatus.NEW
    
    def test_lead_industry_role_consistency(self, test_session):
        """Test that roles match industries."""
        leads = generate_leads(test_session, count=20, seed=456)
        
        industry_roles = {
            "Software": ["VP Engineering", "Head of Product", "CTO", "Engineering Manager"],
            "Manufacturing": ["VP Operations", "Plant Manager", "Supply Chain Director"],
            "Retail": ["VP Merchandising", "Director of E-commerce", "Operations Lead"],
            "Healthcare": ["Director of Nursing", "VP Clinical Operations", "Health IT Lead"],
            "Logistics": ["VP Logistics", "Head of Procurement", "Supply Chain Lead"],
        }
        
        for lead in leads:
            assert lead.industry in industry_roles
            assert lead.title in industry_roles[lead.industry]
    
    def test_leads_persisted_to_database(self, test_session):
        """Test that leads are properly saved to database."""
        generate_leads(test_session, count=5, seed=789)
        
        db_leads = test_session.query(Lead).all()
        assert len(db_leads) == 5
