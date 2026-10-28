from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class Database:
    def __init__(self, url: str):
        options = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False, "timeout": 15}
            if ":memory:" in url or url.endswith("sqlite://"):
                options["poolclass"] = StaticPool
            elif "/.local/" in url:
                Path(".local").mkdir(exist_ok=True)
        self.engine = create_engine(url, **options)
        if url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def sqlite_foreign_keys(connection, _record):
                connection.execute("PRAGMA foreign_keys=ON")
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    def dispose(self):
        self.engine.dispose()
