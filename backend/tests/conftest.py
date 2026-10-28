import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from app.config import Settings
from app.db import Database
from app.main import create_app
from app.models import Base, User
from app.security import hash_password

PASSWORD = "TestOnly-Training42!"
ORIGIN = "http://testserver"


@dataclass
class Clock:
    now: datetime = datetime(2026, 10, 28, 8, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


class Actor:
    def __init__(self, app, email):
        self.client = TestClient(app)
        result = self.client.post("/api/auth/login", json={"email": email, "password": PASSWORD}, headers={"Origin": ORIGIN})
        assert result.status_code == 200, result.text
        self.auth = result.json()
        self.user = self.auth["user"]
        self.csrf = self.auth["csrf_token"]

    def get(self, path, **kwargs):
        return self.client.get(path, **kwargs)

    def post(self, path, body=None, **kwargs):
        headers = {"Origin": ORIGIN, "X-CSRF-Token": self.csrf}
        headers.update(kwargs.pop("headers", {}))
        return self.client.post(path, json=body, headers=headers, **kwargs)


@pytest.fixture(scope="session")
def encoded_password():
    return hash_password(PASSWORD)


@pytest.fixture
def world(tmp_path, encoded_password):
    url = os.getenv("APP_TEST_DATABASE_URL") or f"sqlite+pysqlite:///{(tmp_path/'timedesk-test.sqlite3').as_posix()}"
    if not url.startswith("sqlite") and "test" not in (make_url(url).database or "").lower():
        raise RuntimeError("APP_TEST_DATABASE_URL must name a dedicated test database")
    database = Database(url)
    Base.metadata.drop_all(database.engine)
    Base.metadata.create_all(database.engine)
    clock = Clock()
    app = create_app(Settings(database_url=url, allowed_origins=(ORIGIN,), cookie_secure=False), database, clock)
    with database.session_factory.begin() as db:
        m1 = User(email="manager@test.example", name="Training Manager", role="manager", password_hash=encoded_password)
        m2 = User(email="manager2@test.example", name="Training Second Manager", role="manager", password_hash=encoded_password)
        db.add_all([m1,m2]); db.flush()
        db.add_all([
            User(email="employee@test.example", name="Training Employee", role="employee", manager_id=m1.id, password_hash=encoded_password),
            User(email="colleague@test.example", name="Training Colleague", role="employee", manager_id=m1.id, password_hash=encoded_password),
            User(email="outside@test.example", name="Training Outside", role="employee", manager_id=m2.id, password_hash=encoded_password),
        ])
    actors = {key:Actor(app,email) for key,email in [("manager","manager@test.example"),("manager2","manager2@test.example"),("employee","employee@test.example"),("colleague","colleague@test.example"),("outside","outside@test.example")]}
    yield SimpleNamespace(app=app, db=database, clock=clock, **actors)
    for actor in actors.values():
        actor.client.close()
    Base.metadata.drop_all(database.engine)
    database.dispose()
