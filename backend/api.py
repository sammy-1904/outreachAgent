"""FastAPI app with real-time SSE streaming, pipeline control, and MCP tool endpoints."""
from __future__ import annotations

import asyncio
import csv
import io
import json
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Generator, Optional
from queue import Queue

from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .db import SessionLocal, init_db
from .logging_utils import configure_logging
from .config import get_settings
from .mcp_server import MCPEndpoints
from .models import Lead, LeadStatus, LogEntry, Message
from .lead_generator import generate_leads
from .enricher import enrich_leads
from .message_generator import generate_messages
from .sender import send_messages
from .tracking import log_event, start_run, finish_run, count_statuses

settings = get_settings()
configure_logging(getattr(settings, "log_level", "INFO"))
init_db()

app = FastAPI(title="Outreach Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global pipeline state
pipeline_state = {
    "running": False,
    "current_stage": None,
    "should_stop": False,
    "run_id": None,
    "progress": {
        "generate": {"status": "pending", "count": 0},
        "enrich": {"status": "pending", "count": 0},
        "message": {"status": "pending", "count": 0},
        "send": {"status": "pending", "count": 0, "sent": 0, "failed": 0},
    }
}

# Event queues for SSE
event_subscribers: list[Queue] = []


def broadcast_event(event_type: str, data: dict):
    """Broadcast event to all SSE subscribers."""
    event = {"type": event_type, "data": data, "timestamp": datetime.utcnow().isoformat()}
    for queue in event_subscribers:
        queue.put(event)


@contextmanager
def get_db_session() -> Generator:
    """Context manager for database sessions with proper cleanup."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class RunRequest(BaseModel):
    dry_run: bool = True
    ai_mode: bool = False
    seed: int | None = None
    count: int = 200


class GenerateLeadsRequest(BaseModel):
    count: int = 200
    seed: int | None = None


class EnrichLeadsRequest(BaseModel):
    ai_mode: bool = False
    limit: int | None = None


class GenerateMessagesRequest(BaseModel):
    ai_mode: bool = False
    limit: int | None = None


class SendOutreachRequest(BaseModel):
    dry_run: bool = True


# ---------------- SSE Streaming Endpoint ----------------

@app.get("/events")
async def event_stream(request: Request):
    """Server-Sent Events endpoint for real-time updates."""
    queue: Queue = Queue()
    event_subscribers.append(queue)
    
    async def generate():
        try:
            # Send initial state
            yield {
                "event": "init",
                "data": json.dumps({
                    "pipeline_state": pipeline_state,
                    "timestamp": datetime.utcnow().isoformat()
                })
            }
            
            while True:
                if await request.is_disconnected():
                    break
                
                try:
                    # Non-blocking check for events
                    while not queue.empty():
                        event = queue.get_nowait()
                        yield {
                            "event": event["type"],
                            "data": json.dumps(event["data"])
                        }
                except:
                    pass
                
                await asyncio.sleep(0.1)
        finally:
            if queue in event_subscribers:
                event_subscribers.remove(queue)
    
    return EventSourceResponse(generate())


# ---------------- Pipeline Control Endpoints ----------------

@app.post("/pipeline/start")
async def start_pipeline(body: RunRequest, background_tasks: BackgroundTasks):
    """Start the pipeline in background with real-time updates."""
    global pipeline_state
    
    if pipeline_state["running"]:
        return {"status": "error", "message": "Pipeline already running"}
    
    # Reset state
    pipeline_state = {
        "running": True,
        "current_stage": "starting",
        "should_stop": False,
        "run_id": None,
        "progress": {
            "generate": {"status": "pending", "count": 0},
            "enrich": {"status": "pending", "count": 0},
            "message": {"status": "pending", "count": 0},
            "send": {"status": "pending", "count": 0, "sent": 0, "failed": 0},
        }
    }
    
    broadcast_event("pipeline_started", {"config": body.model_dump()})
    
    # Run pipeline in a thread pool to avoid blocking the event loop
    import concurrent.futures
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, run_pipeline_sync_wrapper, body)
    
    return {"status": "ok", "message": "Pipeline started"}


@app.post("/pipeline/stop")
async def stop_pipeline():
    """Stop the running pipeline."""
    global pipeline_state
    
    if not pipeline_state["running"]:
        return {"status": "error", "message": "No pipeline running"}
    
    pipeline_state["should_stop"] = True
    broadcast_event("pipeline_stopping", {"message": "Stop requested"})
    
    return {"status": "ok", "message": "Stop signal sent"}


@app.get("/pipeline/status")
async def get_pipeline_status():
    """Get current pipeline status."""
    with get_db_session() as session:
        status_counts = {
            status.value: session.query(Lead).filter(Lead.status == status).count()
            for status in LeadStatus
        }
        total = sum(status_counts.values())
    
    return {
        "pipeline_state": pipeline_state,
        "metrics": {"total": total, "status_counts": status_counts}
    }


def run_pipeline_sync_wrapper(config: RunRequest):
    """Synchronous wrapper to run pipeline in a thread pool."""
    run_pipeline_core(config)


def run_pipeline_core(config: RunRequest):
    """Run pipeline stages with real-time broadcasting (runs in thread)."""
    global pipeline_state
    
    try:
        with get_db_session() as session:
            # Start run tracking
            run_id = start_run(
                session, 
                mode="dry" if config.dry_run else "live",
                ai_mode=config.ai_mode,
                seed=config.seed,
                total=config.count
            )
            pipeline_state["run_id"] = run_id
            
            # Stage 1: Generate Leads
            if pipeline_state["should_stop"]:
                raise InterruptedError("Pipeline stopped by user")
            
            pipeline_state["current_stage"] = "generate"
            pipeline_state["progress"]["generate"]["status"] = "running"
            broadcast_event("stage_started", {"stage": "generate"})
            
            leads = generate_leads(session, count=config.count, seed=config.seed)
            
            pipeline_state["progress"]["generate"]["status"] = "completed"
            pipeline_state["progress"]["generate"]["count"] = len(leads)
            broadcast_event("stage_completed", {
                "stage": "generate",
                "count": len(leads)
            })
            
            # Stage 2: Enrich Leads
            if pipeline_state["should_stop"]:
                raise InterruptedError("Pipeline stopped by user")
            
            pipeline_state["current_stage"] = "enrich"
            pipeline_state["progress"]["enrich"]["status"] = "running"
            broadcast_event("stage_started", {"stage": "enrich"})
            
            enriched = enrich_leads(session, ai_mode=config.ai_mode)
            
            pipeline_state["progress"]["enrich"]["status"] = "completed"
            pipeline_state["progress"]["enrich"]["count"] = len(enriched)
            
            # Broadcast metrics immediately after enrichment
            enrich_statuses = count_statuses(session)
            broadcast_event("stage_completed", {
                "stage": "enrich",
                "count": len(enriched)
            })
            broadcast_event("metrics_update", {
                "total": sum(enrich_statuses.values()),
                "status_counts": enrich_statuses
            })
            
            # Stage 3: Generate Messages
            if pipeline_state["should_stop"]:
                raise InterruptedError("Pipeline stopped by user")
            
            pipeline_state["current_stage"] = "message"
            pipeline_state["progress"]["message"]["status"] = "running"
            broadcast_event("stage_started", {"stage": "message"})
            
            messages = generate_messages(session, ai_mode=config.ai_mode)
            
            pipeline_state["progress"]["message"]["status"] = "completed"
            pipeline_state["progress"]["message"]["count"] = len(messages)
            broadcast_event("stage_completed", {
                "stage": "message",
                "count": len(messages)
            })
            
            # Stage 4: Send Outreach
            if pipeline_state["should_stop"]:
                raise InterruptedError("Pipeline stopped by user")
            
            pipeline_state["current_stage"] = "send"
            pipeline_state["progress"]["send"]["status"] = "running"
            broadcast_event("stage_started", {"stage": "send"})
            
            sent = send_messages(session, dry_run=config.dry_run)
            
            # Count results
            statuses = count_statuses(session)
            sent_count = statuses.get("SENT", 0)
            failed_count = statuses.get("FAILED", 0)
            
            pipeline_state["progress"]["send"]["status"] = "completed"
            pipeline_state["progress"]["send"]["sent"] = sent_count
            pipeline_state["progress"]["send"]["failed"] = failed_count
            broadcast_event("stage_completed", {
                "stage": "send",
                "sent": sent_count,
                "failed": failed_count
            })
            
            # Finish run
            finish_run(session, run_id, succeeded=sent_count, failed=failed_count)
            
            pipeline_state["current_stage"] = "completed"
            broadcast_event("pipeline_completed", {
                "run_id": run_id,
                "total": config.count,
                "sent": sent_count,
                "failed": failed_count
            })
            
    except InterruptedError as e:
        pipeline_state["current_stage"] = "stopped"
        broadcast_event("pipeline_stopped", {"message": str(e)})
    except Exception as e:
        pipeline_state["current_stage"] = "error"
        broadcast_event("pipeline_error", {"error": str(e)})
    finally:
        pipeline_state["running"] = False
        pipeline_state["should_stop"] = False


# ---------------- Legacy Run Endpoint ----------------

@app.post("/run")
def run_pipeline_sync(body: RunRequest):
    """Run the full pipeline synchronously (legacy endpoint)."""
    with get_db_session() as session:
        run_id = start_run(
            session,
            mode="dry" if body.dry_run else "live",
            ai_mode=body.ai_mode,
            seed=body.seed,
            total=body.count
        )
        
        leads = generate_leads(session, count=body.count, seed=body.seed)
        enriched = enrich_leads(session, ai_mode=body.ai_mode)
        messages = generate_messages(session, ai_mode=body.ai_mode)
        sent = send_messages(session, dry_run=body.dry_run)
        
        statuses = count_statuses(session)
        finish_run(session, run_id, 
                   succeeded=statuses.get("SENT", 0),
                   failed=statuses.get("FAILED", 0))
        
    return {
        "status": "ok",
        "summary": {
            "run_id": run_id,
            "generated": len(leads),
            "enriched": len(enriched),
            "messaged": len(messages),
            "sent": len(sent),
            "status_counts": statuses
        }
    }


# ---------------- Metrics & Status Endpoints ----------------

@app.get("/metrics")
def metrics():
    """Get pipeline metrics and status counts."""
    with get_db_session() as session:
        status_counts = {
            status.value: session.query(Lead).filter(Lead.status == status).count()
            for status in LeadStatus
        }
        total = sum(status_counts.values())
    return {"total": total, "status_counts": status_counts}


@app.get("/leads")
def leads(status: str | None = None, limit: int = 50, offset: int = 0):
    """Get paginated list of leads with optional status filter."""
    with get_db_session() as session:
        query = session.query(Lead)
        if status:
            query = query.filter(Lead.status == LeadStatus(status))
        results = query.order_by(Lead.id.desc()).offset(offset).limit(limit).all()
        payload = [
            {
                "id": lead.id,
                "name": lead.full_name,
                "company": lead.company,
                "title": lead.title,
                "industry": lead.industry,
                "email": lead.email,
                "status": lead.status.value,
                "confidence": lead.confidence,
                "pains": lead.pains,
                "triggers": lead.triggers,
                "last_error": lead.last_error,
            }
            for lead in results
        ]
    return {"items": payload}


@app.get("/logs")
def logs(limit: int = 100):
    """Get recent log entries."""
    with get_db_session() as session:
        entries = (
            session.query(LogEntry)
            .order_by(LogEntry.ts.desc())
            .limit(limit)
            .all()
        )
        payload = [
            {
                "ts": entry.ts.isoformat(),
                "stage": entry.stage,
                "level": entry.level,
                "message": entry.message,
                "lead_id": entry.lead_id,
            }
            for entry in entries
        ]
    return {"items": payload}


@app.get("/leads/{lead_id}/messages")
def get_lead_messages(lead_id: int):
    """Get all messages for a specific lead."""
    with get_db_session() as session:
        lead = session.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return {"error": "Lead not found", "messages": []}
        
        messages = (
            session.query(Message)
            .filter(Message.lead_id == lead_id)
            .order_by(Message.id.desc())
            .all()
        )
        
        payload = {
            "lead": {
                "id": lead.id,
                "name": lead.full_name,
                "email": lead.email,
                "company": lead.company,
                "title": lead.title,
                "status": lead.status.value,
            },
            "messages": [
                {
                    "id": msg.id,
                    "email_a": msg.email_a,
                    "email_b": msg.email_b,
                    "dm_a": msg.dm_a,
                    "dm_b": msg.dm_b,
                    "cta": msg.cta,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                }
                for msg in messages
            ]
        }
    return payload


# ---------------- MCP Tool Discovery ----------------

@app.get("/mcp/tools")
def list_mcp_tools():
    """MCP Protocol: List all available tools with their JSON schemas."""
    return {
        "tools": [
            {
                "name": "generate_leads",
                "description": "Generate synthetic B2B leads with realistic company and contact data",
                "endpoint": "/tools/generate_leads",
                "method": "POST",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer", "description": "Number of leads to generate", "default": 200},
                        "seed": {"type": "integer", "description": "Random seed for reproducibility", "nullable": True}
                    }
                }
            },
            {
                "name": "enrich_leads",
                "description": "Enrich leads with company size, persona, pain points, and triggers",
                "endpoint": "/tools/enrich_leads",
                "method": "POST",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ai_mode": {"type": "boolean", "description": "Use AI (Groq) for enrichment", "default": False},
                        "limit": {"type": "integer", "description": "Max leads to enrich", "nullable": True}
                    }
                }
            },
            {
                "name": "generate_messages",
                "description": "Generate personalized email and LinkedIn DM messages with A/B variants",
                "endpoint": "/tools/generate_messages",
                "method": "POST",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ai_mode": {"type": "boolean", "description": "Use AI for message generation", "default": False},
                        "limit": {"type": "integer", "description": "Max messages to generate", "nullable": True}
                    }
                }
            },
            {
                "name": "send_outreach",
                "description": "Send outreach messages via email and LinkedIn DM",
                "endpoint": "/tools/send_outreach",
                "method": "POST",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dry_run": {"type": "boolean", "description": "Simulate sending without actual delivery", "default": True}
                    }
                }
            },
            {
                "name": "get_status",
                "description": "Get current pipeline status and metrics",
                "endpoint": "/tools/get_status",
                "method": "GET",
                "inputSchema": {"type": "object", "properties": {}}
            }
        ],
        "version": "1.0",
        "protocol": "MCP"
    }


# ---------------- MCP Tool Endpoints ----------------

@app.post("/tools/generate_leads")
def tool_generate_leads(body: GenerateLeadsRequest):
    """MCP Tool: Generate sample leads."""
    global pipeline_state
    pipeline_state["running"] = True
    pipeline_state["current_stage"] = "generate"
    pipeline_state["progress"]["generate"]["status"] = "running"
    broadcast_event("stage_started", {"stage": "generate"})
    
    with get_db_session() as session:
        mcp = MCPEndpoints(session)
        result = mcp.tool_generate_leads(count=body.count, seed=body.seed)
        # Update state and broadcast completion
        pipeline_state["progress"]["generate"]["status"] = "completed"
        pipeline_state["progress"]["generate"]["count"] = result.get("generated", 0)
        statuses = count_statuses(session)
        broadcast_event("stage_completed", {"stage": "generate", "count": result.get("generated", 0)})
        broadcast_event("metrics_update", {"total": sum(statuses.values()), "status_counts": statuses})
    return {"status": "ok", "result": result}


@app.post("/tools/enrich_leads")
def tool_enrich_leads(body: EnrichLeadsRequest):
    """MCP Tool: Enrich leads with company/persona data."""
    global pipeline_state
    pipeline_state["running"] = True
    pipeline_state["current_stage"] = "enrich"
    pipeline_state["progress"]["enrich"]["status"] = "running"
    broadcast_event("stage_started", {"stage": "enrich"})
    
    with get_db_session() as session:
        mcp = MCPEndpoints(session)
        result = mcp.tool_enrich_leads(ai_mode=body.ai_mode, limit=body.limit)
        # Update state and broadcast completion
        pipeline_state["progress"]["enrich"]["status"] = "completed"
        pipeline_state["progress"]["enrich"]["count"] = result.get("enriched", 0)
        statuses = count_statuses(session)
        broadcast_event("stage_completed", {"stage": "enrich", "count": result.get("enriched", 0)})
        broadcast_event("metrics_update", {"total": sum(statuses.values()), "status_counts": statuses})
    return {"status": "ok", "result": result}


@app.post("/tools/generate_messages")
def tool_generate_messages(body: GenerateMessagesRequest):
    """MCP Tool: Generate personalized email and LinkedIn messages."""
    global pipeline_state
    pipeline_state["running"] = True
    pipeline_state["current_stage"] = "message"
    pipeline_state["progress"]["message"]["status"] = "running"
    broadcast_event("stage_started", {"stage": "message"})
    
    with get_db_session() as session:
        mcp = MCPEndpoints(session)
        result = mcp.tool_generate_messages(ai_mode=body.ai_mode, limit=body.limit)
        # Update state and broadcast completion
        pipeline_state["progress"]["message"]["status"] = "completed"
        pipeline_state["progress"]["message"]["count"] = result.get("messages", 0)
        statuses = count_statuses(session)
        broadcast_event("stage_completed", {"stage": "message", "count": result.get("messages", 0)})
        broadcast_event("metrics_update", {"total": sum(statuses.values()), "status_counts": statuses})
    return {"status": "ok", "result": result}


@app.post("/tools/send_outreach")
def tool_send_outreach(body: SendOutreachRequest):
    """MCP Tool: Send outreach messages (email + LinkedIn DM)."""
    global pipeline_state
    pipeline_state["running"] = True
    pipeline_state["current_stage"] = "send"
    pipeline_state["progress"]["send"]["status"] = "running"
    broadcast_event("stage_started", {"stage": "send"})
    
    with get_db_session() as session:
        mcp = MCPEndpoints(session)
        result = mcp.tool_send_outreach(dry_run=body.dry_run)
        # Update state and broadcast completion
        statuses = count_statuses(session)
        sent = statuses.get("SENT", 0)
        failed = statuses.get("FAILED", 0)
        pipeline_state["progress"]["send"]["status"] = "completed"
        pipeline_state["progress"]["send"]["sent"] = sent
        pipeline_state["progress"]["send"]["failed"] = failed
        pipeline_state["running"] = False
        pipeline_state["current_stage"] = None
        broadcast_event("stage_completed", {"stage": "send", "sent": sent, "failed": failed})
        broadcast_event("metrics_update", {"total": sum(statuses.values()), "status_counts": statuses})
        broadcast_event("pipeline_completed", {"sent": sent, "failed": failed, "total": sum(statuses.values())})
    return {"status": "ok", "result": result}


@app.get("/tools/get_status")
def tool_get_status():
    """MCP Tool: Get current pipeline status and metrics."""
    with get_db_session() as session:
        mcp = MCPEndpoints(session)
        result = mcp.tool_get_metrics()
    return {"status": "ok", "result": result}


# ---------------- Database Management ----------------

@app.post("/reset")
def reset_database():
    """Clear all leads and messages for fresh start."""
    with get_db_session() as session:
        session.query(Message).delete()
        session.query(LogEntry).delete()
        session.query(Lead).delete()
        session.commit()
    return {"status": "ok", "message": "Database cleared"}


# ---------------- Targeting Rules Configuration ----------------

@app.get("/config/targeting-rules")
def get_targeting_rules():
    """Get current targeting rules configuration."""
    from .enricher import load_targeting_rules
    rules = load_targeting_rules()
    return {"status": "ok", "rules": rules}


@app.put("/config/targeting-rules")
def update_targeting_rules(rules: dict):
    """Update targeting rules configuration."""
    import json
    from pathlib import Path
    from .enricher import reload_targeting_rules, RULES_FILE
    
    try:
        # Validate structure
        required_keys = ["company_size_rules", "persona_rules", "pain_points", "triggers"]
        for key in required_keys:
            if key not in rules:
                return {"status": "error", "message": f"Missing required key: {key}"}
        
        # Write to file
        with open(RULES_FILE, 'w', encoding='utf-8') as f:
            json.dump(rules, f, indent=2)
        
        # Reload cache
        updated_rules = reload_targeting_rules()
        
        return {"status": "ok", "message": "Targeting rules updated", "rules": updated_rules}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---------------- Export Endpoints ----------------

@app.get("/export/leads")
def export_leads_csv():
    """Export all leads as CSV."""
    with get_db_session() as session:
        leads_data = session.query(Lead).order_by(Lead.id).all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "full_name", "company", "title", "industry", "website",
            "email", "linkedin", "country", "company_size", "persona",
            "pains", "triggers", "confidence", "status", "last_error"
        ])
        
        for lead in leads_data:
            writer.writerow([
                lead.id, lead.full_name, lead.company, lead.title,
                lead.industry, lead.website, lead.email, lead.linkedin,
                lead.country, lead.company_size, lead.persona, lead.pains,
                lead.triggers, lead.confidence, lead.status.value, lead.last_error
            ])
        
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=leads.csv"}
        )


@app.get("/export/messages")
def export_messages_csv():
    """Export all messages as CSV."""
    with get_db_session() as session:
        messages_data = (
            session.query(Message, Lead)
            .join(Lead, Message.lead_id == Lead.id)
            .order_by(Message.id)
            .all()
        )
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "message_id", "lead_id", "lead_name", "lead_email",
            "email_a", "email_b", "dm_a", "dm_b", "cta", "created_at"
        ])
        
        for msg, lead in messages_data:
            writer.writerow([
                msg.id, msg.lead_id, lead.full_name, lead.email,
                msg.email_a, msg.email_b, msg.dm_a, msg.dm_b,
                msg.cta, msg.created_at.isoformat() if msg.created_at else ""
            ])
        
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=messages.csv"}
        )
