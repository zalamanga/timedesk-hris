from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError

import app.main as main
from app.models import Attendance, Correction, Event, Session, User
from conftest import ORIGIN, PASSWORD


def check_in(actor, request_id=None):
    result = actor.post("/api/attendance/check-in", {"request_id":request_id or str(uuid4())})
    assert result.status_code == 201, result.text
    return result.json()


def completed(world, actor=None, hours=8):
    actor = actor or world.employee
    row = check_in(actor)
    world.clock.advance(hours=hours)
    result = actor.post(f"/api/attendance/{row['id']}/check-out", {"expected_version":row['version']})
    assert result.status_code == 200, result.text
    return result.json()


def propose(actor, entry, **overrides):
    payload = {"expected_version":entry["version"], "proposed_start":(datetime.fromisoformat(entry["start_at"])-timedelta(minutes=15)).isoformat(),
               "proposed_end":entry["end_at"], "reason":"Training: memperbaiki catatan jam masuk"}
    payload.update(overrides)
    return actor.post(f"/api/attendance/{entry['id']}/corrections", payload)


def pending(world):
    entry = completed(world)
    response = propose(world.employee,entry)
    assert response.status_code == 201,response.text
    return entry,response.json()


def counts(world):
    with world.db.session_factory() as db:
        return {model.__name__:db.scalar(select(func.count()).select_from(model)) for model in (Attendance,Correction,Event)}


def test_lifecycle_server_clock_and_events(world):
    entry = check_in(world.employee)
    assert entry["start_at"] == world.clock.now.isoformat()
    world.clock.advance(hours=7,minutes=45)
    result = world.employee.post(f"/api/attendance/{entry['id']}/check-out",{"expected_version":1})
    assert result.status_code==200
    assert result.json()["duration"]=="07:45"
    assert result.json()["version"]==2
    detail = world.employee.get(f"/api/attendance/{entry['id']}").json()
    assert [row["kind"] for row in detail["events"]]==["check_in","check_out"]


def test_retry_same_intent_returns_current_entry_without_event(world):
    intent=str(uuid4()); entry=check_in(world.employee,intent)
    world.clock.advance(minutes=30)
    world.employee.post(f"/api/attendance/{entry['id']}/check-out",{"expected_version":1})
    result=world.employee.post("/api/attendance/check-in",{"request_id":intent})
    assert result.status_code==200
    assert result.json()["id"]==entry["id"] and result.json()["end_at"]
    assert counts(world)=={"Attendance":1,"Correction":0,"Event":2}


def test_new_intent_while_active_conflicts(world):
    check_in(world.employee)
    assert world.employee.post("/api/attendance/check-in",{"request_id":str(uuid4())}).status_code==409
    assert counts(world)["Event"]==1


@pytest.mark.parametrize("field,value",[("start_at","2020-01-01T00:00:00Z"),("end_at","2020-01-01T00:00:00Z"),("employee_id",2)])
def test_client_cannot_supply_clock_or_other_employee(world,field,value):
    assert world.employee.post("/api/attendance/check-in",{"request_id":str(uuid4()),field:value}).status_code==422
    assert counts(world)["Attendance"]==0


@pytest.mark.parametrize("actor",["manager","colleague","outside","manager2"])
def test_others_cannot_punch_out_employee(world,actor):
    entry=check_in(world.employee); world.clock.advance(hours=1)
    assert getattr(world,actor).post(f"/api/attendance/{entry['id']}/check-out",{"expected_version":1}).status_code==404
    assert counts(world)["Event"]==1


def test_checkout_same_time_and_stale_version(world):
    entry=check_in(world.employee)
    assert world.employee.post(f"/api/attendance/{entry['id']}/check-out",{"expected_version":1}).status_code==409
    world.clock.advance(seconds=2)
    assert world.employee.post(f"/api/attendance/{entry['id']}/check-out",{"expected_version":2}).status_code==409
    assert world.employee.post(f"/api/attendance/{entry['id']}/check-out",{"expected_version":1}).status_code==200
    assert world.employee.post(f"/api/attendance/{entry['id']}/check-out",{"expected_version":1}).status_code==409


def test_correction_approval_applies_once_and_audit(world):
    entry,row=pending(world)
    before=world.employee.get(f"/api/attendance/{entry['id']}").json()
    assert before["start_at"]==entry["start_at"]
    result=world.manager.post(f"/api/corrections/{row['id']}/approve",{"expected_version":1,"note":"Training: catatan sudah diverifikasi"})
    assert result.status_code==200,result.text
    assert result.json()["state"]=="approved"
    updated=world.employee.get(f"/api/attendance/{entry['id']}").json()
    assert updated["start_at"]==row["proposed_start"] and updated["version"]==3
    assert updated["events"][-1]["kind"]=="correction_approved"
    assert row["original_start"]==entry["start_at"] and row["original_end"]==entry["end_at"]
    decided=world.employee.get(f"/api/corrections/{row['id']}").json()
    assert decided["original_start"]==entry["start_at"] and decided["original_end"]==entry["end_at"]
    summary=updated["events"][-1]["summary"]
    assert entry["start_at"] in summary and entry["end_at"] in summary and row["proposed_start"] in summary
    assert world.manager.post(f"/api/corrections/{row['id']}/approve",{"expected_version":1}).status_code==409
    assert counts(world)["Event"]==4


@pytest.mark.parametrize("action,state",[("reject","rejected"),("withdraw","withdrawn")])
def test_reject_or_withdraw_leaves_original(world,action,state):
    entry,row=pending(world)
    actor=world.manager if action=="reject" else world.employee
    result=actor.post(f"/api/corrections/{row['id']}/{action}",{"expected_version":1,"note":"Training: catatan belum cukup"})
    assert result.status_code==200 and result.json()["state"]==state
    original=world.employee.get(f"/api/attendance/{entry['id']}").json()
    assert original["start_at"]==entry["start_at"] and original["version"]==2


def test_reject_requires_note(world):
    _,row=pending(world)
    assert world.manager.post(f"/api/corrections/{row['id']}/reject",{"expected_version":1,"note":"short"}).status_code==422
    assert counts(world)["Event"]==3


def test_only_one_pending_correction(world):
    entry,_=pending(world)
    assert propose(world.employee,entry).status_code==409
    assert counts(world)["Correction"]==1


@pytest.mark.parametrize("actor",["manager2","outside","colleague"])
def test_correction_privacy_detail_list_count_and_csv(world,actor):
    entry,row=pending(world); actor=getattr(world,actor)
    assert actor.get(f"/api/corrections/{row['id']}").status_code==404
    assert actor.get(f"/api/attendance/{entry['id']}").status_code==404
    listed=actor.get("/api/corrections?state=all").json()
    assert listed["items"]==[] and listed["total"]==0
    assert row["reason"] not in actor.get("/api/attendance/export.csv?from_date=2026-10-28&to_date=2026-10-29").text
    assert actor.post(f"/api/corrections/{row['id']}/approve",{"expected_version":1}).status_code==404


def test_manager_direct_reports_only(world):
    check_in(world.employee);check_in(world.outside)
    result=world.manager.get("/api/attendance?from_date=2026-10-28&to_date=2026-10-28&scope=team").json()
    assert {row["employee"]["id"] for row in result["items"]}=={world.employee.user["id"]}
    endpoint=f"?from_date=2026-10-28&to_date=2026-10-28&scope=team&employee_id={world.outside.user['id']}"
    for path in ("/api/attendance","/api/recap","/api/attendance/export.csv"):
        assert world.manager.get(path+endpoint).status_code==404


def test_employee_team_access_denied(world):
    for path in ("/api/team","/api/corrections?scope=team","/api/recap?from_date=2026-10-28&to_date=2026-10-28&scope=team"):
        assert world.employee.get(path).status_code==403


@pytest.mark.parametrize("changes",[
    {"reason":"short"},
    {"proposed_start":"2026-10-28T08:00:00","proposed_end":"2026-10-28T16:00:00"},
    {"proposed_start":"2026-10-28T16:00:00Z","proposed_end":"2026-10-28T08:00:00Z"},
    {"proposed_start":"2026-10-26T08:00:00Z","proposed_end":"2026-10-28T16:00:00Z"},
    {"proposed_end":"2026-10-28T17:00:00Z"},
])
def test_correction_input_validation(world,changes):
    entry=completed(world)
    assert propose(world.employee,entry,**changes).status_code==422
    assert counts(world)["Correction"]==0


def test_active_entry_cannot_be_corrected(world):
    entry=check_in(world.employee)
    assert propose(world.employee,entry,proposed_end=world.clock.now.isoformat()).status_code in (409,422)


def test_approval_rechecks_entry_version(world):
    entry,row=pending(world)
    with world.db.session_factory.begin() as db:
        db.get(Attendance,entry["id"]).version+=1
    assert world.manager.post(f"/api/corrections/{row['id']}/approve",{"expected_version":1}).status_code==409
    assert world.employee.get(f"/api/corrections/{row['id']}").json()["state"]=="pending"


def test_adjacent_allowed_but_overlap_rejected(world):
    first=completed(world,hours=2)
    second=completed(world,hours=2)
    assert propose(world.employee,second,proposed_start=first["end_at"]).status_code==201
    third=completed(world,hours=1)
    assert propose(world.employee,third,proposed_start=second["start_at"]).status_code==422


def test_approval_rechecks_overlap_against_new_entry(world):
    entry,row=pending(world)
    # A second interval can appear between proposal and review through another approved correction/import.
    with world.db.session_factory.begin() as db:
        start=datetime.fromisoformat(row["proposed_start"])
        db.add(Attendance(employee_id=world.employee.user["id"],request_id=str(uuid4()),start_at=start,end_at=start+timedelta(minutes=10),version=1))
    result=world.manager.post(f"/api/corrections/{row['id']}/approve",{"expected_version":1})
    assert result.status_code==409
    assert world.employee.get(f"/api/attendance/{entry['id']}").json()["start_at"]==entry["start_at"]


def test_atomic_rollback_when_audit_insert_fails(world):
    entry,row=pending(world)
    def fail(_mapper,_connection,target):
        if target.kind=="correction_approved":raise RuntimeError("injected audit failure")
    event.listen(Event,"before_insert",fail)
    try:
        with pytest.raises(RuntimeError,match="injected audit failure"):
            world.manager.post(f"/api/corrections/{row['id']}/approve",{"expected_version":1})
    finally:
        event.remove(Event,"before_insert",fail)
    with world.db.session_factory() as db:
        assert db.get(Attendance,entry["id"]).version==2
        assert db.get(Correction,row["id"]).state=="pending"
    assert counts(world)["Event"]==3


def test_midnight_clips_by_wib_day_and_window(world):
    world.clock.now=datetime(2026,10,28,16,tzinfo=timezone.utc) # 23:00 WIB
    completed(world,hours=4)
    result=world.employee.get("/api/recap?from_date=2026-10-28&to_date=2026-10-29").json()
    assert [row["completed_seconds"] for row in result["items"]]==[3600,10800]
    assert result["completed_seconds"]==14400
    clipped=world.employee.get("/api/recap?from_date=2026-10-29&to_date=2026-10-29").json()
    assert clipped["completed_seconds"]==10800
    csv=world.employee.get("/api/attendance/export.csv?from_date=2026-10-29&to_date=2026-10-29")
    assert ",10800,03:00" in csv.text


def test_active_duration_excluded_completed_totals(world):
    completed(world,hours=1);check_in(world.employee);world.clock.advance(minutes=30)
    result=world.employee.get("/api/recap?from_date=2026-10-28&to_date=2026-10-28").json()
    assert result["completed_seconds"]==3600 and result["active_seconds"]==1800


@pytest.mark.parametrize("from_date,to_date",[("2026-10-28","2026-10-27"),("2026-09-01","2026-10-28"),("nonsense","2026-10-28")])
def test_range_validation(world,from_date,to_date):
    for path in ("/api/attendance","/api/recap","/api/attendance/export.csv"):
        assert world.employee.get(f"{path}?from_date={from_date}&to_date={to_date}").status_code==422


@pytest.mark.parametrize("date",["9999-12-31","0001-01-01","1999-12-31","2201-01-01"])
def test_out_of_supported_year_range_returns_422_instead_of_overflow(world,date):
    for path in ("/api/attendance","/api/recap","/api/attendance/export.csv"):
        response=world.employee.get(f"{path}?from_date={date}&to_date={date}")
        assert response.status_code==422
        assert "2000" in response.json()["detail"]


def test_team_cap_applies_to_lists_reports_and_filtered_employee_can_still_be_read(world,monkeypatch):
    monkeypatch.setattr(main,"MAX_TEAM_USERS",1)
    query="from_date=2026-10-28&to_date=2026-10-28&scope=team"
    for path in ("/api/team","/api/corrections?scope=team",f"/api/attendance?{query}",f"/api/recap?{query}",f"/api/attendance/export.csv?{query}"):
        response=world.manager.get(path)
        assert response.status_code==422,response.text
    for path in ("/api/attendance","/api/recap","/api/attendance/export.csv"):
        response=world.manager.get(f"{path}?{query}&employee_id={world.employee.user['id']}")
        assert response.status_code==200,response.text
        assert "Training Outside" not in response.text
    assert world.manager.get(f"/api/team?employee_id={world.employee.user['id']}").status_code==200
    assert world.manager.get(f"/api/corrections?scope=team&employee_id={world.employee.user['id']}").status_code==200


def test_report_entry_cap_counts_real_filtered_entries_consistently(world,monkeypatch):
    monkeypatch.setattr(main,"MAX_REPORT_ENTRIES",1)
    completed(world,hours=1)
    query="from_date=2026-10-28&to_date=2026-10-28"
    assert world.employee.get(f"/api/recap?{query}").status_code==200
    assert world.employee.get(f"/api/attendance/export.csv?{query}").status_code==200
    completed(world,hours=1)
    for path in ("/api/recap","/api/attendance/export.csv"):
        response=world.employee.get(f"{path}?{query}")
        assert response.status_code==422 and "Persempit" in response.json()["detail"]
    # Other employees' report rows are excluded before enforcing the cap.
    assert world.colleague.get(f"/api/recap?{query}").status_code==200


def test_first_snapshot_survives_later_approved_corrections(world):
    entry,first=pending(world)
    result=world.manager.post(f"/api/corrections/{first['id']}/approve",{"expected_version":1})
    assert result.status_code==200
    updated=result.json()["entry"]
    response=propose(world.employee,updated)
    assert response.status_code==201,response.text
    second=response.json()
    assert second["original_start"]==first["proposed_start"]
    assert world.manager.post(f"/api/corrections/{second['id']}/approve",{"expected_version":1}).status_code==200
    history=world.employee.get(f"/api/corrections/{first['id']}").json()
    assert history["original_start"]==entry["start_at"]
    assert history["original_end"]==entry["end_at"]
    assert history["entry"]["start_at"]!=history["original_start"]


def test_csv_formula_escape_and_reason_omitted(world):
    completed(world)
    with world.db.session_factory.begin() as db:
        db.get(User,world.employee.user["id"]).name="=SUM(1+1)"
    result=world.manager.get("/api/attendance/export.csv?from_date=2026-10-28&to_date=2026-10-28&scope=team")
    assert result.status_code==200 and "'=SUM(1+1)" in result.text
    assert "reason" not in result.text.lower()


def test_database_partial_unique_active_constraint(world):
    check_in(world.employee)
    with world.db.session_factory() as db:
        db.add(Attendance(employee_id=world.employee.user["id"],request_id=str(uuid4()),start_at=world.clock.now,end_at=None,version=1))
        with pytest.raises(IntegrityError):db.commit()


@pytest.mark.parametrize("header,value",[("X-CSRF-Token","bad"),("Origin","https://untrusted.example"),("Sec-Fetch-Site","cross-site")])
def test_csrf_origin_guards(world,header,value):
    result=world.employee.post("/api/attendance/check-in",{"request_id":str(uuid4())},headers={header:value})
    assert result.status_code==403 and counts(world)["Attendance"]==0


def test_oversized_and_non_json_bodies_rejected(world):
    headers={"Origin":ORIGIN,"X-CSRF-Token":world.employee.csrf}
    result=world.employee.client.post("/api/attendance/check-in",content='{"request_id":"'+('x'*65536)+'"}',headers={**headers,"Content-Type":"application/json"})
    assert result.status_code==413
    result=world.employee.client.post("/api/attendance/check-in",content="request_id=x",headers={**headers,"Content-Type":"application/x-www-form-urlencoded"})
    assert result.status_code==415
    assert counts(world)["Attendance"]==0


def test_unauthenticated_read_and_write_rejected(world):
    with TestClient(world.app) as client:
        assert client.get("/api/attendance?from_date=2026-10-28&to_date=2026-10-28").status_code==401
        assert client.post("/api/attendance/check-in",json={"request_id":str(uuid4())},headers={"Origin":ORIGIN}).status_code==401


def test_colleague_cannot_propose_or_withdraw_other_record(world):
    entry,row=pending(world)
    assert propose(world.colleague,entry).status_code==404
    assert world.manager.post(f"/api/corrections/{row['id']}/withdraw",{"expected_version":1}).status_code==404
    assert world.employee.post(f"/api/corrections/{row['id']}/approve",{"expected_version":1}).status_code==404


def test_session_expiry_cookie_and_logout(world):
    raw=world.employee.client.cookies.get("timedesk_session")
    with world.db.session_factory() as db:
        assert raw not in {row.token_hash for row in db.scalars(select(Session))}
    result=world.employee.get("/api/auth/me")
    assert result.headers["cache-control"]=="no-store"
    assert world.employee.post("/api/auth/logout").status_code==204
    assert world.employee.get("/api/auth/me").status_code==401
    world.clock.advance(hours=25)
    assert world.manager.get("/api/auth/me").status_code==401


def test_rate_limit_wrong_credentials(world):
    with TestClient(world.app) as client:
        for _ in range(8):
            assert client.post("/api/auth/login",json={"email":"unknown@test.example","password":"wrong"},headers={"Origin":ORIGIN}).status_code==401
        result=client.post("/api/auth/login",json={"email":"unknown@test.example","password":"wrong"},headers={"Origin":ORIGIN})
        assert result.status_code==429 and int(result.headers["retry-after"])>0


def concurrent_post(world,actor,path,bodies):
    barrier=Barrier(len(bodies))
    def one(body):
        with TestClient(world.app) as client:
            client.cookies.update(actor.client.cookies)
            barrier.wait(timeout=10)
            return client.post(path,json=body,headers={"Origin":ORIGIN,"X-CSRF-Token":actor.csrf})
    with ThreadPoolExecutor(max_workers=len(bodies)) as pool:
        return list(pool.map(one,bodies))


@pytest.mark.parametrize("same_intent",[True,False])
def test_postgres_racing_checkin_exactly_one_event(world,same_intent):
    if world.db.engine.dialect.name!="postgresql":pytest.skip("Requires PostgreSQL row locks")
    intent=str(uuid4())
    bodies=[{"request_id":intent if same_intent else str(uuid4())} for _ in range(2)]
    responses=concurrent_post(world,world.employee,"/api/attendance/check-in",bodies)
    assert sorted(row.status_code for row in responses)==([200,201] if same_intent else [201,409])
    assert counts(world)=={"Attendance":1,"Correction":0,"Event":1}


def test_postgres_racing_correction_decision_one_winner(world):
    if world.db.engine.dialect.name!="postgresql":pytest.skip("Requires PostgreSQL row locks")
    entry,row=pending(world)
    responses=concurrent_post(world,world.manager,f"/api/corrections/{row['id']}/approve",[{"expected_version":1},{"expected_version":1}])
    assert sorted(response.status_code for response in responses)==[200,409]
    assert counts(world)["Event"]==4
    assert world.employee.get(f"/api/attendance/{entry['id']}").json()["version"]==3
