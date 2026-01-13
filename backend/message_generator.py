"""Personalized message generation for email and LinkedIn DM with A/B variants.

Supports both AI-powered (Groq) and template-based message generation.
"""
from __future__ import annotations

import os
import time
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from .models import Lead, LeadStatus, Message
from .logging_utils import get_logger
from .tracking import log_event
from .config import get_settings

logger = get_logger(__name__)
settings = get_settings()

CTA = "Would you be open to a 15-minute call next week?"

# Word limits as per assignment requirements
EMAIL_MAX_WORDS = 120
DM_MAX_WORDS = 60

# Rate limiting for Groq API
GROQ_MESSAGE_INTERVAL = 3.0  # seconds between API calls
_last_message_request_time = 0.0


def _truncate_to_word_limit(text: str, max_words: int) -> str:
    """Truncate text to a maximum number of words while keeping it readable."""
    words = text.split()
    if len(words) <= max_words:
        return text
    truncated = " ".join(words[:max_words])
    if not truncated.endswith((".", "!", "?")):
        truncated = truncated.rstrip(",;:") + "..."
    return truncated


def _wait_for_rate_limit():
    """Enforce rate limiting between Groq API calls."""
    global _last_message_request_time
    
    now = time.time()
    time_since_last = now - _last_message_request_time
    
    if time_since_last < GROQ_MESSAGE_INTERVAL:
        wait_time = GROQ_MESSAGE_INTERVAL - time_since_last
        logger.info("⏳ Rate limiting: waiting %.1f seconds before next message generation...", wait_time)
        time.sleep(wait_time)
    
    _last_message_request_time = time.time()


def _generate_messages_with_groq(lead: Lead) -> Dict[str, str]:
    """Generate personalized messages using Groq AI."""
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY not set")
    
    try:
        from groq import Groq
    except ImportError as e:
        logger.error("❌ Failed to import Groq library: %s", e)
        raise
    
    os.environ["GROQ_API_KEY"] = settings.groq_api_key
    client = Groq()
    
    system_prompt = """You are an expert B2B sales copywriter. Generate highly personalized outreach messages.
Return ONLY a valid JSON object (no markdown, no explanation) with these exact keys:
- email_a: A pain-focused email (max 120 words). Empathize with their challenges.
- email_b: A trigger/opportunity-focused email (max 120 words). Highlight timing and opportunity.
- dm_a: A brief LinkedIn DM (max 60 words). Pain-focused, conversational.
- dm_b: A brief LinkedIn DM (max 60 words). Opportunity-focused, forward-looking.

Each message MUST:
1. Use their first name
2. Reference their specific company and role
3. Mention specific pain points or triggers relevant to THEM
4. Sound natural and human, not salesy
5. End with a clear CTA for a 15-minute call

Make each variant genuinely different in tone and approach, not just word swaps."""

    user_prompt = f"""Generate personalized outreach messages for this lead:

Name: {lead.full_name}
Title: {lead.title}
Company: {lead.company}
Industry: {lead.industry}
Country: {lead.country}
Company Size: {lead.company_size or 'Unknown'}
Persona: {lead.persona or 'Business Leader'}
Pain Points: {lead.pains or 'Operational challenges'}
Buying Triggers: {lead.triggers or 'Growth initiatives'}

Write 4 unique, compelling messages that would make {lead.full_name.split()[0]} want to respond."""

    try:
        _wait_for_rate_limit()
        
        logger.info("📤 Generating AI messages for: %s (%s)", lead.full_name, lead.company)
        
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,  # Higher temperature for more creative variety
            max_tokens=800,
        )
        
        content = completion.choices[0].message.content
        logger.info(" AI messages received! Tokens: %d", 
                   completion.usage.total_tokens if completion.usage else 0)
        
        # Parse JSON response with sanitization
        import json
        import re
        
        text = content.strip()
        
        # Remove markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:]) if len(lines) > 1 else text
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
        
        # Extract JSON object
        if "{" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                text = text[start:end]
        
        # Sanitize control characters inside string values
        # Replace literal newlines inside strings with \n escape sequence
        def sanitize_json_string(match):
            # Replace actual newlines/tabs with escaped versions
            s = match.group(0)
            s = s.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            return s
        
        # Match string values in JSON (between quotes)
        text = re.sub(r'"[^"]*"', sanitize_json_string, text)
        
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # Fallback: try with strict=False
            parsed = json.loads(text, strict=False)
        
        # Helper to extract string from potentially nested response
        def extract_string(value):
            """Extract string from value that might be str, dict, or other."""
            if value is None:
                return ""
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                # Try common keys that might contain the message
                for key in ['body', 'text', 'content', 'message']:
                    if key in value:
                        return str(value[key])
                # Just stringify the whole thing
                return str(value)
            return str(value)
        
        # Ensure word limits and clean up escaped newlines for display
        def clean_message(msg, max_words=EMAIL_MAX_WORDS):
            msg = extract_string(msg)
            if not msg:
                return ""
            # Convert escaped newlines back to actual newlines for readability
            msg = msg.replace('\\n', '\n').replace('\\r', '').replace('\\t', ' ')
            return _truncate_to_word_limit(msg, max_words)
        
        result = {
            "email_a": clean_message(parsed.get("email_a", ""), EMAIL_MAX_WORDS),
            "email_b": clean_message(parsed.get("email_b", ""), EMAIL_MAX_WORDS),
            "dm_a": clean_message(parsed.get("dm_a", ""), DM_MAX_WORDS),
            "dm_b": clean_message(parsed.get("dm_b", ""), DM_MAX_WORDS),
        }
        
        logger.info("✅ AI messages generated for %s", lead.full_name)
        return result
        
    except Exception as e:
        logger.error("❌ AI message generation failed: %s", e)
        raise


# ============== Template-based fallback ==============

def _build_email_variant_a(lead: Lead) -> str:
    """Email variant A: Focus on pain points and empathy."""
    first_name = lead.full_name.split()[0]
    pains = lead.pains or "operational friction"
    persona = lead.persona or "teams"
    
    email = (
        f"Hi {first_name},\n\n"
        f"I noticed your role at {lead.company} in {lead.industry}. "
        f"Many {persona} leaders I work with face similar challenges — {pains}. "
        f"I've helped teams reduce these friction points significantly.\n\n"
        f"{CTA}\n\n"
        f"Best regards"
    )
    return _truncate_to_word_limit(email, EMAIL_MAX_WORDS)


def _build_email_variant_b(lead: Lead) -> str:
    """Email variant B: Focus on triggers and opportunity."""
    first_name = lead.full_name.split()[0]
    triggers = lead.triggers or "upcoming initiatives"
    industry = lead.industry
    
    email = (
        f"Hi {first_name},\n\n"
        f"With {triggers} happening in {industry}, teams like yours at {lead.company} "
        f"often see this as the right moment to optimize operations. "
        f"I'd love to share a quick framework that's helped similar organizations.\n\n"
        f"{CTA}\n\n"
        f"Cheers"
    )
    return _truncate_to_word_limit(email, EMAIL_MAX_WORDS)


def _build_dm_variant_a(lead: Lead) -> str:
    """LinkedIn DM variant A: Brief, pain-focused opener."""
    first_name = lead.full_name.split()[0]
    pains = (lead.pains or "common challenges").split(";")[0].strip()
    
    dm = (
        f"Hi {first_name} — noticed your work at {lead.company}. "
        f"Many in similar roles tackle {pains}. "
        f"Happy to share a 10-min teardown if useful. {CTA}"
    )
    return _truncate_to_word_limit(dm, DM_MAX_WORDS)


def _build_dm_variant_b(lead: Lead) -> str:
    """LinkedIn DM variant B: Trigger-based, forward-looking."""
    first_name = lead.full_name.split()[0]
    triggers = (lead.triggers or "growth phase").split(";")[0].strip()
    
    dm = (
        f"Hi {first_name} — saw your profile and {lead.company}'s momentum. "
        f"With {triggers}, now could be ideal timing to streamline operations. "
        f"Quick call? {CTA}"
    )
    return _truncate_to_word_limit(dm, DM_MAX_WORDS)


def _generate_messages_template(lead: Lead) -> Dict[str, str]:
    """Generate messages using templates (fallback when AI is off)."""
    return {
        "email_a": _build_email_variant_a(lead),
        "email_b": _build_email_variant_b(lead),
        "dm_a": _build_dm_variant_a(lead),
        "dm_b": _build_dm_variant_b(lead),
    }


# ============== Main function ==============

def generate_messages(session: Session, limit: int | None = None, ai_mode: bool = False) -> List[Message]:
    """Generate personalized email and DM messages with A/B variants for enriched leads.
    
    Args:
        session: Database session
        limit: Maximum number of leads to process
        ai_mode: If True, use Groq AI for message generation (slower but more personalized)
    """
    query = session.query(Lead).filter(Lead.status == LeadStatus.ENRICHED)
    if limit:
        query = query.limit(limit)
    leads = query.all()

    messages: List[Message] = []
    ai_failures = 0
    
    for lead in leads:
        try:
            if ai_mode:
                try:
                    msg_data = _generate_messages_with_groq(lead)
                except Exception as e:
                    logger.warning("AI message generation failed for %s, using template: %s", 
                                 lead.full_name, e)
                    msg_data = _generate_messages_template(lead)
                    ai_failures += 1
            else:
                msg_data = _generate_messages_template(lead)

            msg = Message(
                lead_id=lead.id,
                email_a=msg_data["email_a"],
                email_b=msg_data["email_b"],
                dm_a=msg_data["dm_a"],
                dm_b=msg_data["dm_b"],
                cta=CTA,
            )
            session.add(msg)
            lead.status = LeadStatus.MESSAGED
            messages.append(msg)
            
        except Exception as e:
            logger.error("Failed to generate messages for lead %s: %s", lead.id, e)

    session.commit()
    
    mode_str = "AI" if ai_mode else "template"
    if ai_failures > 0:
        logger.info("Generated messages for %s leads (%s mode, %d AI failures)", 
                   len(messages), mode_str, ai_failures)
    else:
        logger.info("Generated messages for %s leads (%s mode)", len(messages), mode_str)
    
    log_event(session, stage="message", level="INFO", 
              message=f"Generated messages for {len(messages)} leads (ai_mode={ai_mode})")
    return messages
