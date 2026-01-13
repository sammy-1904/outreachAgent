"""SQLAlchemy models and enums for the outreach pipeline."""
from __future__ import annotations

import enum
from datetime import datetime
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, Float
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    ENRICHED = "ENRICHED"
    MESSAGED = "MESSAGED"
    SENT = "SENT"
    FAILED = "FAILED"


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String, nullable=False)
    company = Column(String, nullable=False)
    title = Column(String, nullable=False)
    industry = Column(String, nullable=False)
    website = Column(String, nullable=False)
    email = Column(String, nullable=False)
    linkedin = Column(String, nullable=False)
    country = Column(String, nullable=False)

    company_size = Column(String, nullable=True)
    persona = Column(String, nullable=True)
    pains = Column(Text, nullable=True)
    triggers = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)

    status = Column(Enum(LeadStatus), default=LeadStatus.NEW, nullable=False)
    last_error = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    messages = relationship("Message", back_populates="lead")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    email_a = Column(Text, nullable=True)
    email_b = Column(Text, nullable=True)
    dm_a = Column(Text, nullable=True)
    dm_b = Column(Text, nullable=True)
    cta = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    lead = relationship("Lead", back_populates="messages")


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    mode = Column(String, nullable=False)
    ai_mode = Column(String, nullable=False)
    seed = Column(Integer, nullable=True)
    total = Column(Integer, nullable=True)
    succeeded = Column(Integer, default=0, nullable=False)
    failed = Column(Integer, default=0, nullable=False)


class LogEntry(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    stage = Column(String, nullable=False)
    level = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    ts = Column(DateTime, default=datetime.utcnow, nullable=False)

    lead = relationship("Lead")
    run = relationship("Run")
