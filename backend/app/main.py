import csv
import io
import secrets
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import and_, case, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session as OrmSession

from .config import Settings
from .db import Database
from .intervals import JAKARTA, clip_seconds, hhmm, iso, window
from .models import Attendance, Correction, Event, RateLimitBucket, Session, User, utcnow
from .schemas import CheckIn, Decision, Login, ProposeCorrection, Version
from .security import new_token, token_hash, verify_password

COOKIE = "timedesk_session"
MAX_TEAM_USERS = 500
MAX_REPORT_ENTRIES = 10000


def get_db(request: Request):
    with request.app.state.database.session_factory() as db:
        yield db


DB = Annotated[OrmSession, Depends(get_db)]


def get_auth(request: Request, db: DB):
    token = request.cookies.get(COOKIE, "")
    if not token or len(token) > 128:
        raise HTTPException(401, "Silakan masuk terlebih dahulu")
    auth = db.scalar(select(Session).where(Session.token_hash == token_hash(token)))
    if auth is None or auth.expires_at <= request.app.state.clock() or not auth.user.is_active:
        raise HTTPException(401, "Sesi berakhir. Silakan masuk kembali")
    return auth


Auth = Annotated[Session, Depends(get_auth)]


def mutation_auth(request: Request, auth: Auth):
    csrf = request.headers.get("x-csrf-token", "")
    if not csrf or not secrets.compare_digest(csrf.encode(), auth.csrf_token.encode()):
        raise HTTPException(403, "Token CSRF tidak valid. Muat ulang sesi")
    return auth


MutationAuth = Annotated[Session, Depends(mutation_auth)]


def person(user):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "manager_id": user.manager_id}


def session_response(auth, settings):
    return {"user": person(auth.user), "csrf_token": auth.csrf_token, "demo_mode": settings.demo_mode}


def consume_login(db, peer, email, now, settings):
    from datetime import timezone
    seconds = settings.login_window_seconds
    start = datetime.fromtimestamp(int(now.timestamp()) // seconds * seconds, tz=timezone.utc)
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    counts = []
    for scope, identity in (("peer", peer), ("email", email)):
        key = token_hash(f"{scope}:{identity}")
        statement = insert(RateLimitBucket).values(key=key, window_start=start, attempts=1)
        statement = statement.on_conflict_do_update(index_elements=[RateLimitBucket.key], set_={
            "window_start": start, "attempts": case((RateLimitBucket.window_start == start, RateLimitBucket.attempts + 1), else_=1),
        }).returning(RateLimitBucket.attempts)
        counts.append(db.execute(statement).scalar_one())
    db.execute(delete(RateLimitBucket).where(RateLimitBucket.window_start < now - timedelta(days=2)))
    db.commit()
    if counts[0] > settings.login_ip_limit or counts[1] > settings.login_limit:
        raise HTTPException(429, "Terlalu banyak percobaan masuk. Coba lagi nanti", headers={"Retry-After": str(max(1, int((start + timedelta(seconds=seconds) - now).total_seconds())))})


def scope_ids(db, user, scope, employee_id=None):
    if scope == "team":
        if user.role != "manager":
            raise HTTPException(403, "Hanya manajer dapat membuka rekap tim")
        filters = [User.manager_id == user.id, User.is_active.is_(True)]
        if employee_id is not None:
            filters.append(User.id == employee_id)
        ids = list(db.scalars(select(User.id).where(*filters).limit(MAX_TEAM_USERS + 1)))
        if len(ids) > MAX_TEAM_USERS:
            raise HTTPException(422, f"Tim melebihi {MAX_TEAM_USERS} karyawan. Pilih employee_id tertentu untuk mempersempit cakupan")
    else:
        ids = [user.id]
    if employee_id is not None:
        if employee_id not in ids:
            raise HTTPException(404, "Karyawan tidak ditemukan")
        ids = [employee_id]
    return ids


def readable(user, employee):
    return user.id == employee.id or (user.role == "manager" and employee.manager_id == user.id)


def entry_data(entry, now):
    seconds = max(0, int(((entry.end_at or now) - entry.start_at).total_seconds()))
    return {"id": entry.id, "employee": person(entry.employee), "start_at": iso(entry.start_at), "end_at": iso(entry.end_at),
            "version": entry.version, "seconds": seconds if entry.end_at else 0, "duration": hhmm(seconds) if entry.end_at else None,
            "active_seconds": seconds if entry.end_at is None else 0, "request_id": entry.request_id}


def correction_data(correction, now):
    return {"id": correction.id, "entry": entry_data(correction.entry, now), "employee": person(correction.employee),
            "original_start": iso(correction.original_start), "original_end": iso(correction.original_end),
            "proposed_start": iso(correction.proposed_start), "proposed_end": iso(correction.proposed_end),
            "reason": correction.reason, "state": correction.state, "version": correction.version,
            "base_entry_version": correction.base_entry_version, "created_at": iso(correction.created_at),
            "decided_at": iso(correction.decided_at), "decided_by_id": correction.decided_by_id,
            "decision_note": correction.decision_note}


def lock_employee(db, employee_id):
    # Every attendance mutation acquires this same row before entry/correction rows.
    return db.scalar(select(User).where(User.id == employee_id).with_for_update().execution_options(populate_existing=True))


def lock_entry(db, entry_id, user, *, owner=False):
    entry = db.get(Attendance, entry_id)
    if entry is None or (entry.employee_id != user.id if owner else not readable(user, entry.employee)):
        raise HTTPException(404, "Catatan kehadiran tidak ditemukan")
    lock_employee(db, entry.employee_id)
    return db.scalar(select(Attendance).where(Attendance.id == entry_id).with_for_update().execution_options(populate_existing=True))


def require_version(row, version):
    if row.version != version:
        raise HTTPException(409, "Data berubah. Muat ulang sebelum mengirim kembali; draf Anda tetap tersimpan")


def has_overlap(db, employee_id, start, end, exclude_id=None):
    clauses = [Attendance.employee_id == employee_id, Attendance.start_at < end,
               or_(Attendance.end_at.is_(None), Attendance.end_at > start)]
    if exclude_id is not None:
        clauses.append(Attendance.id != exclude_id)
    return db.scalar(select(Attendance.id).where(*clauses).limit(1)) is not None


def audit(db, entry, actor, kind, summary, now):
    db.add(Event(entry_id=entry.id, actor_id=actor.id, kind=kind, summary=summary, created_at=now))


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Catatan aktif atau koreksi sudah dibuat. Muat ulang") from None
    except OperationalError as error:
        db.rollback()
        if db.bind.dialect.name == "sqlite" and "locked" in str(error).lower():
            raise HTTPException(409, "Catatan sedang diubah. Muat ulang") from None
        raise


def csv_cell(value):
    value = str(value) if value is not None else ""
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")) else value


def create_app(settings: Settings | None = None, database: Database | None = None, clock: Callable[[], datetime] = utcnow):
    settings = settings or Settings()
    app = FastAPI(title="TimeDesk API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.state.database = database or Database(settings.database_url)
    app.state.settings = settings
    app.state.clock = clock

    @app.middleware("http")
    async def guards(request: Request, call_next):
        if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            if request.headers.get("origin") is not None and request.headers["origin"] not in settings.allowed_origins:
                return JSONResponse({"detail": "Origin tidak diizinkan"}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Permintaan lintas situs ditolak"}, status_code=403)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 65536:
                    return JSONResponse({"detail": "Permintaan melebihi 64 KiB"}, status_code=413)
            request._body = bytes(body)
            if body and request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                return JSONResponse({"detail": "Gunakan application/json"}, status_code=415)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/api/health")
    def health(db: DB):
        try:
            db.execute(select(User.id).limit(1))
        except Exception:
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return {"status": "ok"}

    @app.post("/api/auth/login")
    def login(payload: Login, request: Request, response: Response, db: DB):
        now = clock()
        email = payload.email.lower()
        consume_login(db, request.client.host if request.client else "unknown", email, now, settings)
        user = db.scalar(select(User).where(User.email == email))
        if not verify_password(payload.password, user.password_hash if user else None) or not user or not user.is_active:
            raise HTTPException(401, "Email atau sandi salah")
        if request.cookies.get(COOKIE):
            db.execute(delete(Session).where(Session.token_hash == token_hash(request.cookies[COOKIE])))
        db.execute(delete(Session).where(Session.expires_at <= now))
        token = new_token()
        auth = Session(token_hash=token_hash(token), user_id=user.id, user=user, csrf_token=new_token(), created_at=now, expires_at=now + timedelta(hours=settings.session_hours))
        db.add(auth)
        db.commit()
        response.set_cookie(COOKIE, token, httponly=True, secure=settings.cookie_secure, samesite="lax", path="/api", max_age=settings.session_hours * 3600)
        return session_response(auth, settings)

    @app.get("/api/auth/me")
    def me(auth: Auth):
        return session_response(auth, settings)

    @app.post("/api/auth/logout", status_code=204)
    def logout(response: Response, auth: MutationAuth, db: DB):
        db.delete(auth)
        db.commit()
        response.delete_cookie(COOKIE, path="/api", httponly=True, secure=settings.cookie_secure, samesite="lax")

    @app.get("/api/team")
    def team(auth: Auth, db: DB, employee_id: int | None = None):
        ids = scope_ids(db, auth.user, "team", employee_id)
        return {"items": [person(user) for user in db.scalars(select(User).where(User.id.in_(ids)).order_by(User.name, User.id))]}

    @app.get("/api/attendance")
    def attendance(auth: Auth, db: DB, from_date: date, to_date: date, scope: Literal["mine", "team"] = "mine", employee_id: int | None = None):
        low, high = date_window(from_date, to_date)
        ids = scope_ids(db, auth.user, scope, employee_id)
        entries = list(db.scalars(select(Attendance).where(Attendance.employee_id.in_(ids), Attendance.start_at < high, or_(Attendance.end_at.is_(None), Attendance.end_at > low)).order_by(Attendance.start_at.desc(), Attendance.id.desc()).limit(2001)))
        if len(entries) > 2000:
            raise HTTPException(422, "Lebih dari 2000 catatan. Persempit filter")
        now = clock()
        active = db.scalar(select(Attendance).where(Attendance.employee_id == auth.user.id, Attendance.end_at.is_(None)))
        return {"items": [entry_data(row, now) for row in entries], "active": entry_data(active, now) if active else None,
                "server_now": iso(now), "timezone": "Asia/Jakarta"}

    @app.get("/api/attendance/export.csv")
    def export(auth: Auth, db: DB, from_date: date, to_date: date, scope: Literal["mine", "team"] = "mine", employee_id: int | None = None):
        low, high = date_window(from_date, to_date)
        ids = scope_ids(db, auth.user, scope, employee_id)
        entries = list(db.scalars(select(Attendance).where(Attendance.employee_id.in_(ids), Attendance.start_at < high, or_(Attendance.end_at.is_(None), Attendance.end_at > low)).order_by(Attendance.start_at, Attendance.id).limit(MAX_REPORT_ENTRIES + 1)))
        if len(entries) > MAX_REPORT_ENTRIES:
            raise HTTPException(422, f"Ekspor melebihi {MAX_REPORT_ENTRIES} catatan. Persempit tanggal atau employee_id")
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["ID", "Karyawan", "Email", "Mulai WIB", "Selesai WIB", "Status", "Detik selesai dalam rentang", "Durasi HH:MM dalam rentang"])
        for row in entries:
            seconds = clip_seconds(row.start_at, row.end_at, low, high) if row.end_at else 0
            writer.writerow([csv_cell(value) for value in [row.id, row.employee.name, row.employee.email, row.start_at.astimezone(JAKARTA).isoformat(), row.end_at.astimezone(JAKARTA).isoformat() if row.end_at else "", "Selesai" if row.end_at else "Aktif", seconds, hhmm(seconds)]])
        return Response("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="timedesk-attendance.csv"'})

    @app.get("/api/attendance/{entry_id}")
    def detail(entry_id: int, auth: Auth, db: DB):
        row = db.get(Attendance, entry_id)
        if row is None or not readable(auth.user, row.employee):
            raise HTTPException(404, "Catatan kehadiran tidak ditemukan")
        result = entry_data(row, clock())
        result["events"] = [{"id": event.id, "kind": event.kind, "summary": event.summary, "created_at": iso(event.created_at)} for event in db.scalars(select(Event).where(Event.entry_id == row.id).order_by(Event.id))]
        return result

    @app.post("/api/attendance/check-in", status_code=201)
    def check_in(payload: CheckIn, response: Response, auth: MutationAuth, db: DB):
        user = lock_employee(db, auth.user.id)
        request_id = str(payload.request_id)
        existing = db.scalar(select(Attendance).where(Attendance.employee_id == user.id, Attendance.request_id == request_id))
        if existing:
            response.status_code = 200
            return entry_data(existing, clock())
        if db.scalar(select(Attendance.id).where(Attendance.employee_id == user.id, Attendance.end_at.is_(None))):
            raise HTTPException(409, "Masih ada sesi aktif. Catat pulang dahulu")
        now = clock()
        if db.scalar(select(Attendance.id).where(Attendance.employee_id == user.id, Attendance.end_at > now)):
            raise HTTPException(409, "Waktu server mendahului catatan terakhir; hubungi administrator")
        entry = Attendance(employee_id=user.id, request_id=request_id, start_at=now, end_at=None, version=1)
        db.add(entry)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Catatan masuk sudah dibuat. Muat ulang") from None
        audit(db, entry, user, "check_in", "Jam masuk dicatat oleh server", now)
        commit(db)
        return entry_data(entry, now)

    @app.post("/api/attendance/{entry_id}/check-out")
    def check_out(entry_id: int, payload: Version, auth: MutationAuth, db: DB):
        entry = lock_entry(db, entry_id, auth.user, owner=True)
        require_version(entry, payload.expected_version)
        if entry.end_at is not None:
            raise HTTPException(409, "Sesi ini sudah selesai")
        now = clock()
        if now <= entry.start_at:
            raise HTTPException(409, "Jam pulang harus setelah jam masuk")
        entry.end_at, entry.version = now, entry.version + 1
        audit(db, entry, auth.user, "check_out", "Jam pulang dicatat oleh server", now)
        commit(db)
        return entry_data(entry, now)

    @app.post("/api/attendance/{entry_id}/corrections", status_code=201)
    def propose(entry_id: int, payload: ProposeCorrection, auth: MutationAuth, db: DB):
        entry = lock_entry(db, entry_id, auth.user, owner=True)
        require_version(entry, payload.expected_version)
        if entry.end_at is None:
            raise HTTPException(409, "Selesaikan sesi sebelum mengajukan koreksi")
        if auth.user.manager_id is None:
            raise HTTPException(422, "Manajer belum ditetapkan. Hubungi administrator")
        if payload.proposed_end > clock():
            raise HTTPException(422, "Jam selesai usulan tidak boleh di masa depan")
        if db.scalar(select(Correction.id).where(Correction.entry_id == entry.id, Correction.state == "pending")):
            raise HTTPException(409, "Koreksi untuk sesi ini sedang menunggu keputusan")
        if has_overlap(db, entry.employee_id, payload.proposed_start, payload.proposed_end, entry.id):
            raise HTTPException(422, "Interval usulan bertabrakan dengan sesi lain")
        correction = Correction(entry_id=entry.id, employee_id=entry.employee_id, proposed_start=payload.proposed_start,
                                proposed_end=payload.proposed_end, reason=payload.reason, state="pending", version=1,
                                original_start=entry.start_at, original_end=entry.end_at,
                                base_entry_version=entry.version, created_at=clock())
        db.add(correction)
        audit(db, entry, auth.user, "correction_requested", "Koreksi waktu diajukan; interval belum berubah", clock())
        commit(db)
        return correction_data(correction, clock())

    @app.get("/api/corrections")
    def corrections(auth: Auth, db: DB, scope: Literal["mine", "team"] = "mine", state: Literal["pending", "approved", "rejected", "withdrawn", "all"] = "pending", employee_id: int | None = None):
        ids = scope_ids(db, auth.user, scope, employee_id)
        filters = [Correction.employee_id.in_(ids)]
        if state != "all":
            filters.append(Correction.state == state)
        total = db.scalar(select(func.count()).select_from(Correction).where(*filters))
        rows = db.scalars(select(Correction).where(*filters).order_by(Correction.created_at.desc(), Correction.id.desc()).limit(200))
        return {"items": [correction_data(row, clock()) for row in rows], "total": total, "limit": 200}

    @app.get("/api/corrections/{correction_id}")
    def correction_detail(correction_id: int, auth: Auth, db: DB):
        row = db.get(Correction, correction_id)
        if row is None or not readable(auth.user, row.employee):
            raise HTTPException(404, "Koreksi tidak ditemukan")
        return correction_data(row, clock())

    def decide(db, user, correction_id, payload, action):
        row = db.get(Correction, correction_id)
        if row is None or (row.employee_id != user.id if action == "withdraw" else user.role != "manager" or row.employee.manager_id != user.id):
            raise HTTPException(404, "Koreksi tidak ditemukan")
        lock_employee(db, row.employee_id)
        entry = db.scalar(select(Attendance).where(Attendance.id == row.entry_id).with_for_update().execution_options(populate_existing=True))
        row = db.scalar(select(Correction).where(Correction.id == correction_id).with_for_update().execution_options(populate_existing=True))
        require_version(row, payload.expected_version)
        if row.state != "pending":
            raise HTTPException(409, "Koreksi sudah diputuskan atau ditarik")
        if action == "approve":
            require_version(entry, row.base_entry_version)
            if entry.end_at is None or row.proposed_end > clock():
                raise HTTPException(409, "Interval belum dapat disetujui")
            if has_overlap(db, entry.employee_id, row.proposed_start, row.proposed_end, entry.id):
                raise HTTPException(409, "Usulan bertabrakan dengan sesi lain. Tolak dan minta usulan baru")
            before_start, before_end = entry.start_at, entry.end_at
            entry.start_at, entry.end_at, entry.version = row.proposed_start, row.proposed_end, entry.version + 1
        if action == "reject" and len(payload.note.strip()) < 10:
            raise HTTPException(422, "Tulis alasan penolakan minimal 10 karakter")
        row.state = {"approve": "approved", "reject": "rejected", "withdraw": "withdrawn"}[action]
        row.version += 1
        row.decided_at, row.decided_by_id = clock(), user.id
        row.decision_note = payload.note.strip() or None
        summary = f"Koreksi #{row.id}: {row.state}"
        if action == "approve":
            summary += f"; sebelum [{iso(before_start)}, {iso(before_end)}); sesudah [{iso(entry.start_at)}, {iso(entry.end_at)})"
        audit(db, entry, user, f"correction_{row.state}", summary, clock())
        commit(db)
        return correction_data(row, clock())

    @app.post("/api/corrections/{correction_id}/approve")
    def approve(correction_id: int, payload: Decision, auth: MutationAuth, db: DB):
        return decide(db, auth.user, correction_id, payload, "approve")

    @app.post("/api/corrections/{correction_id}/reject")
    def reject(correction_id: int, payload: Decision, auth: MutationAuth, db: DB):
        return decide(db, auth.user, correction_id, payload, "reject")

    @app.post("/api/corrections/{correction_id}/withdraw")
    def withdraw(correction_id: int, payload: Decision, auth: MutationAuth, db: DB):
        return decide(db, auth.user, correction_id, payload, "withdraw")

    @app.get("/api/recap")
    def recap(auth: Auth, db: DB, from_date: date, to_date: date, scope: Literal["mine", "team"] = "mine", employee_id: int | None = None):
        low, high = date_window(from_date, to_date)
        ids = scope_ids(db, auth.user, scope, employee_id)
        users = list(db.scalars(select(User).where(User.id.in_(ids)).order_by(User.name, User.id)))
        entries = list(db.scalars(select(Attendance).where(Attendance.employee_id.in_(ids), Attendance.start_at < high,
                          or_(Attendance.end_at.is_(None), Attendance.end_at > low)).limit(MAX_REPORT_ENTRIES + 1)))
        if len(entries) > MAX_REPORT_ENTRIES:
            raise HTTPException(422, f"Rekap melebihi {MAX_REPORT_ENTRIES} catatan. Persempit tanggal atau employee_id")
        by_employee = {employee.id: [] for employee in users}
        for entry in entries:
            by_employee[entry.employee_id].append(entry)
        now = clock()
        days = []
        current = from_date
        while current <= to_date:
            day_low, day_high = window(current, current)
            for employee in users:
                owned = by_employee[employee.id]
                complete = sum(clip_seconds(row.start_at, row.end_at, day_low, day_high) for row in owned if row.end_at)
                active = sum(clip_seconds(row.start_at, max(now, row.start_at), day_low, day_high) for row in owned if row.end_at is None)
                days.append({"date": current.isoformat(), "employee": person(employee), "completed_seconds": complete,
                             "duration": hhmm(complete), "active_seconds": active})
            current += timedelta(days=1)
        total = sum(row["completed_seconds"] for row in days)
        return {"from_date": from_date, "to_date": to_date, "timezone": "Asia/Jakarta", "items": days,
                "completed_seconds": total, "duration": hhmm(total), "active_seconds": sum(row["active_seconds"] for row in days), "server_now": iso(now)}

    return app


def date_window(from_date, to_date):
    try:
        return window(from_date, to_date)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


app = create_app()
