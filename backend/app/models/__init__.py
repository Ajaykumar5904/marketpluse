from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(30))  # ecommerce|real_estate|recruiting|market_research
    filters: Mapped[dict] = mapped_column(JSON, default=dict)  # keywords, SKUs, locations
    frequency_cron: Mapped[str] = mapped_column(String(64), default="0 6 * * *")
    notify_emails: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|paused|failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    sources: Mapped[list[Source]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(String(2048))
    scraper_type: Mapped[str] = mapped_column(String(20))  # static|javascript|api
    selectors: Mapped[dict] = mapped_column(JSON, default=dict)  # css/xpath or JSON mapping
    expected_fields: Mapped[list] = mapped_column(JSON, default=list)
    frequency_cron: Mapped[str | None] = mapped_column(String(64))
    proxy_url: Mapped[str | None] = mapped_column(String(512))
    robots_allowed: Mapped[bool | None] = mapped_column(Boolean)
    store_raw_html: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    project: Mapped[Project] = relationship(back_populates="sources")


class ScrapingRun(Base):
    __tablename__ = "scraping_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|success|failed
    pages_fetched: Mapped[int] = mapped_column(Integer, default=0)
    items_extracted: Mapped[int] = mapped_column(Integer, default=0)
    validation_failures: Mapped[int] = mapped_column(Integer, default=0)
    missing_fields: Mapped[dict] = mapped_column(JSON, default=dict)  # field -> count, for data-quality view
    error: Mapped[str | None] = mapped_column(Text)


class RawRecord(Base):
    __tablename__ = "raw_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("scraping_runs.id", ondelete="CASCADE"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    html_snapshot: Mapped[str | None] = mapped_column(Text)


class ListingSnapshot(Base):
    """Current state: exactly one row per (source, dedupe_hash)."""
    __tablename__ = "listing_snapshots"
    __table_args__ = (UniqueConstraint("source_id", "dedupe_hash"), Index("ix_snap_price", "price"))
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    dedupe_hash: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(2048))
    brand: Mapped[str | None] = mapped_column(String(120), index=True)
    seller: Mapped[str | None] = mapped_column(String(120))
    location: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    availability: Mapped[str] = mapped_column(String(20), default="unknown")
    rating: Mapped[float | None]
    review_count: Mapped[int | None]
    image_url: Mapped[str | None] = mapped_column(String(2048))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ListingHistory(Base):
    """Append-only: one observation per listing per run."""
    __tablename__ = "listing_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("listing_snapshots.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("scraping_runs.id", ondelete="CASCADE"))
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    availability: Mapped[str] = mapped_column(String(20))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class PriceChange(Base):
    """Change events (name kept from spec; covers all event types)."""
    __tablename__ = "price_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("listing_snapshots.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("scraping_runs.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(30), index=True)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    abs_change: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    pct_change: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class AlertRule(Base):
    __tablename__ = "alert_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    rule_type: Mapped[str] = mapped_column(String(40))
    params: Mapped[dict] = mapped_column(JSON, default=dict)  # e.g. {"min_pct": 10} or {"keywords": [...]}
    channels: Mapped[list] = mapped_column(JSON, default=lambda: ["email", "in_app"])
    webhook_url: Mapped[str | None] = mapped_column(String(2048))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    format: Mapped[str] = mapped_column(String(10))  # pdf|xlsx
    schedule_cron: Mapped[str | None] = mapped_column(String(64))
    recipients: Mapped[list] = mapped_column(JSON, default=list)
    file_path: Mapped[str | None] = mapped_column(String(512))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailLog(Base):
    __tablename__ = "email_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    recipient: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20))  # sent|failed|dev_logged
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str | None] = mapped_column(String(80))
    entity_id: Mapped[int | None]
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
