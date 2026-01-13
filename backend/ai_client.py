"""Groq client for AI enrichment with rate limiting and retry logic."""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

from .config import get_settings
from .logging_utils import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Groq free tier limits: ~30 requests/minute
# We'll be conservative: 20 requests/minute = 3 seconds between requests
GROQ_REQUEST_INTERVAL = 3.0  # seconds between API calls
_last_request_time = 0.0


def _extract_json_block(text: str) -> Dict[str, Any]:
    """Extract JSON object from text; tolerates code fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:]) if len(lines) > 1 else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    if "{" in text:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            text = text[start:end]
    return json.loads(text)


def _wait_for_rate_limit():
    """Enforce rate limiting between Groq API calls."""
    global _last_request_time
    
    now = time.time()
    time_since_last = now - _last_request_time
    
    if time_since_last < GROQ_REQUEST_INTERVAL:
        wait_time = GROQ_REQUEST_INTERVAL - time_since_last
        logger.info("⏳ Rate limiting: waiting %.1f seconds before next Groq call...", wait_time)
        time.sleep(wait_time)
    
    _last_request_time = time.time()


def enrich_lead_with_groq(lead: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
    """
    Enrich a lead using Groq's LLM with rate limiting and retry logic.
    
    Args:
        lead: Lead data dictionary
        max_retries: Maximum number of retry attempts on rate limit errors
    """
    if not settings.groq_api_key:
        logger.error("❌ GROQ_API_KEY is not set!")
        raise RuntimeError("GROQ_API_KEY not set")
    
    api_key_preview = settings.groq_api_key[:10] + "..." if len(settings.groq_api_key) > 10 else "***"
    logger.info("🔑 Groq API Key: %s | Model: %s", api_key_preview, settings.groq_model)

    try:
        from groq import Groq
    except ImportError as e:
        logger.error("❌ Failed to import Groq library: %s", e)
        raise
    
    os.environ["GROQ_API_KEY"] = settings.groq_api_key
    client = Groq()
    
    system_prompt = (
        "You are a B2B lead enrichment assistant. Analyze the lead and return ONLY a valid JSON object "
        "(no markdown, no explanation) with these exact keys:\n"
        "- company_size: one of 'SMB', 'Mid-Market', or 'Enterprise'\n"
        "- persona: a brief description of their role/persona\n"
        "- pains: an array of 2 pain points relevant to their role\n"
        "- triggers: an array of 1-2 buying triggers\n"
        "- confidence: a number from 0-100 representing confidence in the enrichment\n"
        "\nExample: {\"company_size\": \"Mid-Market\", \"persona\": \"Tech Leader\", "
        "\"pains\": [\"scaling challenges\", \"talent retention\"], \"triggers\": [\"recent funding\"], \"confidence\": 75}"
    )
    
    user_prompt = (
        f"Enrich this B2B lead:\n"
        f"- Name: {lead['full_name']}\n"
        f"- Title: {lead['title']}\n"
        f"- Company: {lead['company']}\n"
        f"- Industry: {lead['industry']}\n"
        f"- Country: {lead['country']}"
    )

    for attempt in range(max_retries + 1):
        try:
            # Enforce rate limiting
            _wait_for_rate_limit()
            
            logger.info("📤 [Attempt %d/%d] Sending request for: %s (%s)", 
                       attempt + 1, max_retries + 1, lead['full_name'], lead['company'])
            
            completion = client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=300,
            )
            
            content = completion.choices[0].message.content
            logger.info(" Response received! Tokens: %d", 
                       completion.usage.total_tokens if completion.usage else 0)
            
            parsed = _extract_json_block(content)
            logger.info("✅ Enriched: company_size=%s, confidence=%s",
                       parsed.get('company_size'), parsed.get('confidence'))
            
            return parsed
            
        except Exception as exc:
            error_str = str(exc).lower()
            
            # Check if it's a rate limit error (429)
            if "429" in str(exc) or "rate" in error_str or "too many" in error_str:
                if attempt < max_retries:
                    # Exponential backoff: 10s, 20s, 40s
                    wait_time = 10 * (2 ** attempt)
                    logger.warning("⚠️ Rate limit hit! Waiting %d seconds before retry...", wait_time)
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error("❌ Rate limit exceeded after %d retries", max_retries)
                    raise
            else:
                logger.error("❌ Groq API error: %s - %s", type(exc).__name__, exc)
                raise
    
    raise RuntimeError("Max retries exceeded")


def apply_enrichment_fields(lead_obj, enriched: Dict[str, Any]) -> None:
    """Apply enrichment fields from Groq response to lead object."""
    lead_obj.company_size = enriched.get("company_size")
    lead_obj.persona = enriched.get("persona")
    
    pains = enriched.get("pains")
    triggers = enriched.get("triggers")
    
    if isinstance(pains, list):
        lead_obj.pains = "; ".join(str(p) for p in pains)
    elif isinstance(pains, str):
        lead_obj.pains = pains
        
    if isinstance(triggers, list):
        lead_obj.triggers = "; ".join(str(t) for t in triggers)
    elif isinstance(triggers, str):
        lead_obj.triggers = triggers
        
    confidence = enriched.get("confidence")
    if confidence is not None:
        try:
            lead_obj.confidence = float(confidence)
        except (ValueError, TypeError):
            lead_obj.confidence = None
    
    logger.info("✅ Applied to lead: persona=%s", lead_obj.persona)
