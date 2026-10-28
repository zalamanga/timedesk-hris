from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


def utcnow():
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("Timezone-aware timestamp required")
            return value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        return value


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('employee','manager')", name="ck_user_role"), CheckConstraint("manager_id IS NULL OR manager_id != id", name="ck_not_self_manager"))
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    user: Mapped[User] = relationship()


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("employee_id", "request_id", name="uq_employee_request"),
        CheckConstraint("end_at IS NULL OR end_at > start_at", name="ck_positive_interval"),
        CheckConstraint("version >= 1", name="ck_entry_version"),
        Index("uq_one_active_entry", "employee_id", unique=True, postgresql_where=text("end_at IS NULL"), sqlite_where=text("end_at IS NULL")),
        Index("ix_entry_employee_start", "employee_id", "start_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    start_at: Mapped[datetime] = mapped_column(UTCDateTime)
    end_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    version: Mapped[int] = mapped_column(Integer, default=1)
    employee: Mapped[User] = relationship()


class Correction(Base):
    __tablename__ = "corrections"
    __table_args__ = (
        CheckConstraint("state IN ('pending','approved','rejected','withdrawn')", name="ck_correction_state"),
        CheckConstraint("proposed_end > proposed_start", name="ck_correction_interval"),
        CheckConstraint("original_end > original_start", name="ck_correction_original_interval"),
        CheckConstraint("version >= 1", name="ck_correction_version"),
        Index("uq_one_pending_correction", "entry_id", unique=True, postgresql_where=text("state = 'pending'"), sqlite_where=text("state = 'pending'")),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("attendance.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    original_start: Mapped[datetime] = mapped_column(UTCDateTime)
    original_end: Mapped[datetime] = mapped_column(UTCDateTime)
    proposed_start: Mapped[datetime] = mapped_column(UTCDateTime)
    proposed_end: Mapped[datetime] = mapped_column(UTCDateTime)
    reason: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(20), default="pending")
    base_entry_version: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decision_note: Mapped[str | None] = mapped_column(Text)
    entry: Mapped[Attendance] = relationship()
    employee: Mapped[User] = relationship(foreign_keys=[employee_id])


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("attendance.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(UTCDateTime)
    attempts: Mapped[int] = mapped_column(Integer)


class SeedMarker(Base):
    __tablename__ = "seed_markers"
    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    completed_at: Mapped[datetime] = mapped_column(UTCDateTime)
