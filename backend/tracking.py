"""Utilities to record run metadata and structured log events in the database."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from .models import Run, LogEntry, LeadStatus, Lead
from .logging_utils import get_logger

logger = get_logger(__name__)


def start_run(session: Session, mode: str, ai_mode: bool, seed: Optional[int], total: Optional[int]) -> int:
    run = Run(mode=mode, ai_mode=str(ai_mode), seed=seed, total=total, succeeded=0, failed=0)
    session.add(run)
    session.commit()
    log_event(session, run_id=run.id, stage="run", level="INFO", message="Run started")
    return run.id


def finish_run(session: Session, run_id: int, succeeded: int, failed: int) -> None:
    run = session.query(Run).get(run_id)
    if run:
        run.succeeded = succeeded
        run.failed = failed
        session.commit()
    log_event(session, run_id=run_id, stage="run", level="INFO", message="Run finished")


def log_event(
    session: Session,
    stage: str,
    level: str,
    message: str,
    run_id: Optional[int] = None,
    lead_id: Optional[int] = None,
) -> None:
    entry = LogEntry(run_id=run_id, lead_id=lead_id, stage=stage, level=level, message=message, ts=datetime.utcnow())
    session.add(entry)
    session.commit()
    getattr(logger, level.lower(), logger.info)(f"[{stage}] {message}")


def count_statuses(session: Session) -> dict[str, int]:
    return {
        status.value: session.query(Lead).filter(Lead.status == status).count()
        for status in LeadStatus
    }
