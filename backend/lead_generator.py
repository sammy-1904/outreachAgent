"""Lead generation using Faker with deterministic seeding and basic validity rules."""
from __future__ import annotations

import random
from typing import Iterable, List
from faker import Faker
from sqlalchemy.orm import Session

from .models import Lead, LeadStatus
from .logging_utils import get_logger
from .tracking import log_event

fake = Faker()
logger = get_logger(__name__)

# Simple industry to role mapping to keep leads plausible
INDUSTRY_ROLES = {
    "Software": ["VP Engineering", "Head of Product", "CTO", "Engineering Manager"],
    "Manufacturing": ["VP Operations", "Plant Manager", "Supply Chain Director"],
    "Retail": ["VP Merchandising", "Director of E-commerce", "Operations Lead"],
    "Healthcare": ["Director of Nursing", "VP Clinical Operations", "Health IT Lead"],
    "Logistics": ["VP Logistics", "Head of Procurement", "Supply Chain Lead"],
}

COUNTRIES = ["US", "UK", "CA", "DE", "FR", "IN", "SG", "AU"]


def _valid_email(name: str, domain: str) -> str:
    base = name.lower().replace(" ", ".")
    return f"{base}@{domain}"


def _valid_linkedin(name: str, company: str) -> str:
    slug = "-".join((name + " " + company).lower().split())
    return f"https://www.linkedin.com/in/{slug[:60]}"


def generate_leads(session: Session, count: int = 200, seed: int | None = None) -> List[Lead]:
    if seed is not None:
        Faker.seed(seed)
        random.seed(seed)

    leads: List[Lead] = []
    industries = list(INDUSTRY_ROLES.keys())

    for _ in range(count):
        industry = random.choice(industries)
        name = fake.name()
        company = fake.company()
        domain = fake.domain_name()
        title = random.choice(INDUSTRY_ROLES[industry])
        email = _valid_email(name, domain)
        linkedin = _valid_linkedin(name, company)
        country = random.choice(COUNTRIES)

        lead = Lead(
            full_name=name,
            company=company,
            title=title,
            industry=industry,
            website=f"https://{domain}",
            email=email,
            linkedin=linkedin,
            country=country,
            status=LeadStatus.NEW,
        )
        session.add(lead)
        leads.append(lead)

    session.commit()
    logger.info("Generated %s leads", len(leads))
    log_event(session, stage="generate", level="INFO", message=f"Generated {len(leads)} leads")
    return leads
