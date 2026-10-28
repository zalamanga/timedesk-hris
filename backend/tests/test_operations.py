from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.cli import init_db
from app.config import Settings
from app.db import Database
from app.models import Attendance, Base, Correction, SeedMarker, User
from app.seed import seed_demo
from app.security import verify_password
from app.schemas import valid_email


def test_alembic_initial_schema_and_second_upgrade(tmp_path):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    url=f"sqlite+pysqlite:///{(tmp_path/'migrations.db').as_posix()}"
    init_db(url);init_db(url)
    db=Database(url)
    try:
        with db.engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection),Base.metadata)==[]
        with db.session_factory() as session:
            assert session.scalar(select(func.count()).select_from(User))==0
            assert session.scalar(select(func.count()).select_from(Correction))==0
    finally:db.dispose()


def test_seed_idempotent_does_not_reset_password_or_records(world):
    password="Training-Only42!"
    with world.db.session_factory.begin() as db:
        assert seed_demo(db,password,world.clock()) is True
    with world.db.session_factory.begin() as db:
        count=db.scalar(select(func.count()).select_from(Attendance))
        assert seed_demo(db,"Another-Password42!",world.clock()) is False
        user=db.scalar(select(User).where(User.email=="employee@timedesk.test"))
        assert verify_password(password,user.password_hash)
        assert db.scalar(select(func.count()).select_from(Attendance))==count


def test_seed_failure_is_atomic_and_future_free(world):
    with pytest.raises(ValueError):
        with world.db.session_factory.begin() as db:seed_demo(db,"short",world.clock())
    with world.db.session_factory.begin() as db:
        assert db.get(SeedMarker,"training-v1") is None
        seed_demo(db,"Training-Only42!",world.clock())
    with world.db.session_factory() as db:
        assert not list(db.scalars(select(Attendance).where(Attendance.end_at>world.clock())))
        assert db.scalar(select(func.count()).select_from(SeedMarker))==1


@pytest.mark.parametrize("value",[(),("*",)])
def test_exact_origins_required(value):
    with pytest.raises(ValueError):Settings(allowed_origins=value)


@pytest.mark.parametrize("email",["a@","@example.test","person@localhost","person name@example.test","person@@example.test"])
def test_login_and_cli_share_full_email_shape_validation(email):
    from app.schemas import Login
    with pytest.raises(ValueError):valid_email(email)
    with pytest.raises(ValueError):Login(email=email,password="irrelevant")


def test_cli_rejects_incomplete_email_without_creating_account(tmp_path,monkeypatch,capsys):
    import sys
    from app.cli import main
    monkeypatch.setenv("DATABASE_URL",f"sqlite+pysqlite:///{(tmp_path/'invalid-email.db').as_posix()}")
    monkeypatch.setenv("APP_USER_PASSWORD","Training-Only42!")
    monkeypatch.setattr(sys,"argv",["app.cli","create-user","--email","a@","--name","Training Invalid","--role","employee"])
    with pytest.raises(SystemExit) as result:main()
    assert result.value.code==2
    assert "email" in capsys.readouterr().err


def test_shared_email_validator_normalizes_case_and_surrounding_space():
    assert valid_email(" Person@Example.Test  ")=="person@example.test"
