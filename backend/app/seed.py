from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select, text

from .intervals import JAKARTA
from .models import Attendance, Correction, Event, SeedMarker, User
from .security import hash_password


def seed_demo(db, password, now):
    if not 12 <= len(password) <= 128:
        raise ValueError("APP_DEMO_PASSWORD must contain 12-128 characters")
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(8095, 1)"))
    if db.get(SeedMarker, "training-v1"):
        return False
    emails = ["manager@timedesk.test", "manager2@timedesk.test", "employee@timedesk.test", "colleague@timedesk.test", "second@timedesk.test"]
    if db.scalar(select(User.id).where(User.email.in_(emails)).limit(1)):
        raise ValueError("Training email already exists; no account was overwritten")
    encoded = hash_password(password)
    manager = User(email=emails[0], name="Training Manajer Operasional", role="manager", password_hash=encoded)
    other = User(email=emails[1], name="Training Manajer Cabang", role="manager", password_hash=encoded)
    db.add_all([manager, other])
    db.flush()
    employee = User(email=emails[2], name="Training Karyawan Operasional", role="employee", password_hash=encoded, manager_id=manager.id)
    colleague = User(email=emails[3], name="Training Karyawan Gudang", role="employee", password_hash=encoded, manager_id=manager.id)
    second = User(email=emails[4], name="Training Karyawan Cabang", role="employee", password_hash=encoded, manager_id=other.id)
    db.add_all([employee, colleague, second])
    db.flush()
    local = now.astimezone(JAKARTA)
    previous = (local - timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    rows = []
    for offset in (1, 2, 3):
        start = previous - timedelta(days=offset)
        rows.append(Attendance(employee_id=employee.id, request_id=str(uuid4()), start_at=start, end_at=start + timedelta(hours=8), version=2))
    overnight = (previous - timedelta(days=4)).replace(hour=22)
    rows.extend([
        Attendance(employee_id=employee.id, request_id=str(uuid4()), start_at=overnight, end_at=overnight + timedelta(hours=8), version=2),
        Attendance(employee_id=colleague.id, request_id=str(uuid4()), start_at=previous, end_at=previous + timedelta(hours=7, minutes=30), version=2),
        Attendance(employee_id=second.id, request_id=str(uuid4()), start_at=previous, end_at=previous + timedelta(hours=8), version=2),
    ])
    db.add_all(rows)
    db.flush()
    for row in rows:
        db.add(Event(entry_id=row.id, actor_id=row.employee_id, kind="training_seed", summary="Training: interval selesai untuk latihan", created_at=now))
    entry = rows[0]
    db.add(Correction(entry_id=entry.id, employee_id=employee.id, original_start=entry.start_at, original_end=entry.end_at,
                      proposed_start=entry.start_at - timedelta(minutes=15), proposed_end=entry.end_at,
                      reason="Training: jam masuk perlu dikoreksi setelah pemeriksaan catatan kerja", state="pending", base_entry_version=entry.version,
                      version=1, created_at=now))
    db.add(SeedMarker(name="training-v1", completed_at=now))
    return True
