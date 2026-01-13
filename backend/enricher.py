"""Lead enrichment supporting heuristic (offline) and optional AI mode."""
from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from .models import Lead, LeadStatus
from .logging_utils import get_logger
from .tracking import log_event
from .config import get_settings
from .ai_client import enrich_lead_with_groq, apply_enrichment_fields

logger = get_logger(__name__)
settings = get_settings()

# Path to targeting rules config
RULES_FILE = Path(__file__).parent / "targeting_rules.json"

# Default rules (fallback if config file not found)
_DEFAULT_RULES = {
    "company_size_rules": {
        "Software": "SMB",
        "Manufacturing": "Enterprise",
        "Retail": "Mid-Market",
        "Healthcare": "Mid-Market",
        "Logistics": "Mid-Market",
    },
    "persona_rules": {
        "VP": "Executive",
        "Head": "Department Head",
        "Director": "Director",
        "Manager": "Manager",
        "Lead": "Team Lead",
        "CTO": "C-Suite",
        "CEO": "C-Suite",
        "CFO": "C-Suite",
    },
    "pain_points": {
        "Software": ["Release velocity bottlenecks", "Rising cloud costs", "Technical debt"],
        "Manufacturing": ["Downtime and maintenance", "Supplier risk", "Quality control"],
        "Retail": ["Inventory accuracy", "Cart abandonment", "Customer retention"],
        "Healthcare": ["Staffing shortages", "Compliance overhead", "Patient satisfaction"],
        "Logistics": ["On-time delivery", "Route inefficiency", "Fuel cost management"],
    },
    "triggers": {
        "Software": ["New product launch", "Security incidents", "Scaling challenges"],
        "Manufacturing": ["Line expansions", "New plant", "Automation initiatives"],
        "Retail": ["Peak season", "New store openings", "E-commerce expansion"],
        "Healthcare": ["Regulatory change", "EHR upgrade", "Facility expansion"],
        "Logistics": ["Fuel spikes", "Network redesign", "Fleet modernization"],
    },
    "default_pains": ["Operational inefficiency", "Cost optimization needs"],
    "default_triggers": ["Budget cycle", "Strategic planning phase"],
    "tier1_countries": ["USA", "UK", "Canada", "Germany", "France", "Australia"]
}

# Cache for loaded rules
_cached_rules: Dict[str, Any] = {}


def load_targeting_rules() -> Dict[str, Any]:
    """Load targeting rules from config file, with caching."""
    global _cached_rules
    
    if _cached_rules:
        return _cached_rules
    
    try:
        if RULES_FILE.exists():
            with open(RULES_FILE, 'r', encoding='utf-8') as f:
                _cached_rules = json.load(f)
                logger.info("Loaded targeting rules from %s", RULES_FILE)
        else:
            _cached_rules = _DEFAULT_RULES.copy()
            logger.info("Using default targeting rules (config file not found)")
    except Exception as e:
        logger.warning("Failed to load targeting rules: %s. Using defaults.", e)
        _cached_rules = _DEFAULT_RULES.copy()
    
    return _cached_rules


def reload_targeting_rules() -> Dict[str, Any]:
    """Force reload of targeting rules from config file."""
    global _cached_rules
    _cached_rules = {}
    return load_targeting_rules()


def _persona_from_title(title: str) -> str:
    """Derive persona tag from job title using keyword matching."""
    rules = load_targeting_rules()
    persona_rules = rules.get("persona_rules", {})
    title_lower = title.lower()
    for key, persona in persona_rules.items():
        if key.lower() in title_lower:
            return persona
    return "Professional"


def _safe_sample(items: List[str], k: int) -> List[str]:
    """Safely sample from a list, handling cases where list is smaller than k."""
    if not items:
        return []
    return random.sample(items, min(k, len(items)))


def enrich_leads(
    session: Session, 
    ai_mode: bool = False, 
    limit: Optional[int] = None
) -> List[Lead]:
    """
    Enrich leads in NEW status with company/persona data.
    
    Modes:
    - Offline (ai_mode=False): Uses rule-based heuristics
    - AI (ai_mode=True): Uses Groq LLM with fallback to heuristics
    """
    query = session.query(Lead).filter(Lead.status == LeadStatus.NEW)
    if limit:
        query = query.limit(limit)
    leads = query.all()

    for lead in leads:
        if ai_mode:
            try:
                enriched = enrich_lead_with_groq(
                    {
                        "full_name": lead.full_name,
                        "title": lead.title,
                        "company": lead.company,
                        "industry": lead.industry,
                        "country": lead.country,
                    }
                )
                apply_enrichment_fields(lead, enriched)
            except Exception as exc:
                logger.warning("AI enrichment failed; falling back to heuristics: %s", exc)
                _apply_heuristics(lead)
        else:
            _apply_heuristics(lead)

        lead.status = LeadStatus.ENRICHED

    session.commit()
    logger.info("Enriched %s leads (ai_mode=%s)", len(leads), ai_mode)
    log_event(
        session, 
        stage="enrich", 
        level="INFO", 
        message=f"Enriched {len(leads)} leads ai_mode={ai_mode}"
    )
    return leads


def _apply_heuristics(lead: Lead) -> None:
    """Apply rule-based enrichment to a lead using configurable targeting rules."""
    rules = load_targeting_rules()
    industry = lead.industry
    
    # Get rules from config
    size_rules = rules.get("company_size_rules", {})
    pain_points = rules.get("pain_points", {})
    triggers = rules.get("triggers", {})
    default_pains = rules.get("default_pains", ["Operational inefficiency"])
    default_triggers = rules.get("default_triggers", ["Budget cycle"])
    tier1_countries = rules.get("tier1_countries", ["USA", "UK", "Canada"])
    
    # Company size based on industry
    lead.company_size = size_rules.get(industry, "Mid-Market")
    
    # Persona from job title
    lead.persona = _persona_from_title(lead.title)
    
    # Pain points - safely sample 2, with fallback defaults
    industry_pains = pain_points.get(industry, default_pains)
    sampled_pains = _safe_sample(industry_pains, 2)
    if not sampled_pains:
        sampled_pains = _safe_sample(default_pains, 2)
    lead.pains = "; ".join(sampled_pains)
    
    # Triggers - safely sample 1, with fallback defaults
    industry_triggers = triggers.get(industry, default_triggers)
    sampled_triggers = _safe_sample(industry_triggers, 1)
    if not sampled_triggers:
        sampled_triggers = _safe_sample(default_triggers, 1)
    lead.triggers = "; ".join(sampled_triggers)
    
    # Calculate confidence based on data quality factors
    confidence = 50.0  # Base score
    
    # +15 if industry is known (we have specific rules for it)
    if industry in size_rules:
        confidence += 15.0
    
    # +10-20 based on title seniority
    title_lower = lead.title.lower() if lead.title else ""
    if any(c in title_lower for c in ["cto", "ceo", "cfo", "coo", "vp", "chief"]):
        confidence += 20.0  # C-Suite / VP = high confidence
    elif any(t in title_lower for t in ["director", "head"]):
        confidence += 15.0  # Director level
    elif any(t in title_lower for t in ["manager", "lead", "senior"]):
        confidence += 10.0  # Manager level
    else:
        confidence += random.uniform(5, 12)  # Other roles
    
    # +5-10 based on country (tier 1 markets = higher confidence)
    if lead.country in tier1_countries:
        confidence += 10.0
    else:
        confidence += random.uniform(3, 8)
    
    # Add some randomness (+/- 5%)
    confidence += random.uniform(-5, 5)
    
    # Clamp to valid range
    lead.confidence = round(max(55.0, min(98.0, confidence)), 1)

