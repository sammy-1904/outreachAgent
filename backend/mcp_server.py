"""MCP server exposing pipeline tools with JSON schemas.

This module wraps the Python services and registers them as MCP tools.
The tools can be called via the FastAPI endpoints or directly via MCP protocol.
"""
from __future__ import annotations

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from .lead_generator import generate_leads
from .enricher import enrich_leads
from .message_generator import generate_messages
from .sender import send_messages
from .models import LeadStatus, Lead
from .logging_utils import get_logger

logger = get_logger(__name__)


# JSON Schemas for MCP tool inputs
TOOL_SCHEMAS = {
    "generate_leads": {
        "name": "generate_leads",
        "description": "Generate sample B2B leads with realistic data",
        "inputSchema": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Number of leads to generate",
                    "default": 200
                },
                "seed": {
                    "type": "integer",
                    "description": "Random seed for reproducibility",
                    "nullable": True
                }
            },
            "required": []
        }
    },
    "enrich_leads": {
        "name": "enrich_leads",
        "description": "Enrich leads with company size, persona, pain points, and triggers",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ai_mode": {
                    "type": "boolean",
                    "description": "Use AI for enrichment (requires API key)",
                    "default": False
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of leads to enrich",
                    "nullable": True
                }
            },
            "required": []
        }
    },
    "generate_messages": {
        "name": "generate_messages",
        "description": "Generate personalized email and LinkedIn DM messages with A/B variants",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ai_mode": {
                    "type": "boolean",
                    "description": "Use AI for message generation (requires API key)",
                    "default": False
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of leads to generate messages for",
                    "nullable": True
                }
            },
            "required": []
        }
    },
    "send_outreach": {
        "name": "send_outreach",
        "description": "Send outreach messages via email and LinkedIn (simulated)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, only log messages without sending",
                    "default": True
                }
            },
            "required": []
        }
    },
    "get_metrics": {
        "name": "get_metrics",
        "description": "Get current pipeline status and lead counts by status",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}


class MCPEndpoints:
    """MCP tool implementations for the outreach pipeline."""
    
    def __init__(self, session: Session):
        self.session = session

    def tool_generate_leads(self, count: int = 200, seed: Optional[int] = None) -> Dict[str, Any]:
        """Generate sample leads with realistic B2B data."""
        leads = generate_leads(self.session, count=count, seed=seed)
        return {
            "generated": len(leads),
            "message": f"Successfully generated {len(leads)} leads"
        }

    def tool_enrich_leads(self, ai_mode: bool = False, limit: Optional[int] = None) -> Dict[str, Any]:
        """Enrich NEW leads with company data, persona, pain points, and triggers."""
        leads = enrich_leads(self.session, ai_mode=ai_mode, limit=limit)
        return {
            "enriched": len(leads),
            "ai_mode": ai_mode,
            "message": f"Successfully enriched {len(leads)} leads"
        }

    def tool_generate_messages(self, ai_mode: bool = False, limit: Optional[int] = None) -> Dict[str, Any]:
        """Generate personalized messages for ENRICHED leads."""
        messages = generate_messages(self.session, limit=limit, ai_mode=ai_mode)
        return {
            "messages": len(messages),
            "ai_mode": ai_mode,
            "message": f"Generated {'AI-powered' if ai_mode else 'template-based'} messages for {len(messages)} leads"
        }

    def tool_send_outreach(self, dry_run: bool = True) -> Dict[str, Any]:
        """Send outreach messages to MESSAGED leads."""
        sent = send_messages(self.session, dry_run=dry_run)
        return {
            "sent": len(sent),
            "dry_run": dry_run,
            "message": f"{'Simulated' if dry_run else 'Sent'} outreach for {len(sent)} leads"
        }

    def tool_get_metrics(self) -> Dict[str, Any]:
        """Get current pipeline metrics and status counts."""
        status_counts = {
            status.value: self.session.query(Lead).filter(Lead.status == status).count()
            for status in LeadStatus
        }
        total = sum(status_counts.values())
        return {
            "status_counts": status_counts,
            "total": total,
            "pipeline_stages": ["NEW", "ENRICHED", "MESSAGED", "SENT", "FAILED"]
        }

    @classmethod
    def get_tool_schemas(cls) -> Dict[str, Any]:
        """Return JSON schemas for all MCP tools."""
        return TOOL_SCHEMAS


def get_mcp_tools_list() -> list:
    """Return list of available MCP tools with their schemas."""
    return list(TOOL_SCHEMAS.values())
