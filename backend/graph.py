"""LangGraph-style orchestration of the outreach pipeline.

This is a thin wrapper that sequences MCP tool calls; it can be adapted to a
full LangGraph StateGraph once the MCP client is wired.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Any, Optional, TypedDict
from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, END

from .config import get_settings
from .lead_generator import generate_leads
from .enricher import enrich_leads
from .message_generator import generate_messages
from .sender import send_messages
from .logging_utils import get_logger
from .tracking import start_run, finish_run, log_event, count_statuses
from .models import LeadStatus, Lead

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class RunConfig:
    dry_run: bool = settings.dry_run
    ai_mode: bool = settings.ai_mode
    seed: int | None = None
    count: int = 200


class PipelineState(TypedDict, total=False):
    run_id: int
    dry_run: bool
    ai_mode: bool
    seed: Optional[int]
    count: int


class PipelineRunner:
    """LangGraph-driven pipeline runner with DB-backed state."""

    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def _build_graph(self, session: Session):
        graph = StateGraph(PipelineState)

        def node_generate(state: PipelineState) -> PipelineState:
            log_event(session, stage="generate", level="INFO", message="Generating leads", run_id=state["run_id"])
            generate_leads(session, count=state.get("count", 200), seed=state.get("seed"))
            return state

        def node_enrich(state: PipelineState) -> PipelineState:
            log_event(session, stage="enrich", level="INFO", message="Enriching leads", run_id=state["run_id"])
            enrich_leads(session, ai_mode=state.get("ai_mode", False))
            return state

        def node_message(state: PipelineState) -> PipelineState:
            log_event(session, stage="message", level="INFO", message="Generating messages", run_id=state["run_id"])
            generate_messages(session)
            return state

        def node_send(state: PipelineState) -> PipelineState:
            log_event(session, stage="send", level="INFO", message="Sending messages", run_id=state["run_id"])
            send_messages(
                session,
                dry_run=state.get("dry_run", True),
                rate_limit_per_minute=settings.rate_limit_per_minute,
                max_retries=settings.max_retries,
            )
            return state

        graph.add_node("generate", node_generate)
        graph.add_node("enrich", node_enrich)
        graph.add_node("message", node_message)
        graph.add_node("send", node_send)

        graph.set_entry_point("generate")
        graph.add_edge("generate", "enrich")
        graph.add_edge("enrich", "message")
        graph.add_edge("message", "send")
        graph.add_edge("send", END)
        return graph.compile()

    def run(self, config: RunConfig) -> Dict[str, Any]:
        session = self.session_factory()
        run_id = start_run(session, mode="dry" if config.dry_run else "live", ai_mode=config.ai_mode, seed=config.seed, total=config.count)
        state: PipelineState = {
            "run_id": run_id,
            "dry_run": config.dry_run,
            "ai_mode": config.ai_mode,
            "seed": config.seed,
            "count": config.count,
        }

        app = self._build_graph(session)
        try:
            app.invoke(state)
        except Exception as exc:  # noqa: BLE001
            log_event(session, stage="run", level="ERROR", message=str(exc), run_id=run_id)
            # mark remaining leads as failed
            session.query(Lead).filter(Lead.status != LeadStatus.SENT).update({"status": LeadStatus.FAILED, "last_error": str(exc)})
            session.commit()
            raise
        finally:
            statuses = count_statuses(session)
            finish_run(session, run_id, succeeded=statuses.get(LeadStatus.SENT.value, 0), failed=statuses.get(LeadStatus.FAILED.value, 0))

        summary = {
            "dry_run": config.dry_run,
            "ai_mode": config.ai_mode,
            "count": config.count,
            "run_id": run_id,
            "status_counts": statuses,
        }
        logger.info("Run complete: %s", summary)
        return summary
