import argparse
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from .config import Settings
from .db import Database
from .models import User, utcnow
from .schemas import valid_email
from .security import hash_password
from .seed import seed_demo


def init_db(database_url):
    root = Path(__file__).resolve().parent.parent
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    config.attributes["database_url"] = database_url
    if database_url.startswith("sqlite") and "/.local/" in database_url:
        Path(".local").mkdir(exist_ok=True)
    command.upgrade(config, "head")


def main():
    parser = argparse.ArgumentParser(description="Manage TimeDesk schema and accounts")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("init-db")
    sub.add_parser("seed-demo")
    user = sub.add_parser("create-user")
    user.add_argument("--email", required=True)
    user.add_argument("--name", required=True)
    user.add_argument("--role", choices=("employee", "manager"), required=True)
    user.add_argument("--manager-id", type=int)
    arguments = parser.parse_args()
    settings = Settings()
    if arguments.action == "init-db":
        init_db(settings.database_url)
        print("Schema up to date")
        return
    database = Database(settings.database_url)
    try:
        with database.session_factory.begin() as db:
            if arguments.action == "seed-demo":
                if not settings.demo_mode:
                    raise ValueError("Enable APP_DEMO_MODE=true before creating training records")
                created = seed_demo(db, os.getenv("APP_DEMO_PASSWORD", ""), utcnow())
                print("Training records created" if created else "Training seed already applied; no records changed")
            else:
                password = os.getenv("APP_USER_PASSWORD", "")
                email, name = valid_email(arguments.email), arguments.name.strip()
                if not 12 <= len(password) <= 128:
                    raise ValueError("Set APP_USER_PASSWORD to 12-128 characters")
                if not 1 <= len(name) <= 100:
                    raise ValueError("Provide a valid email and a name of 1-100 characters")
                if db.scalar(select(User.id).where(User.email == email)):
                    raise ValueError("Email exists; no account was changed")
                if arguments.manager_id is not None:
                    manager = db.get(User, arguments.manager_id)
                    if not manager or manager.role != "manager" or not manager.is_active:
                        raise ValueError("Manager must be an active manager account")
                db.add(User(email=email, name=name, role=arguments.role, manager_id=arguments.manager_id, password_hash=hash_password(password)))
                print("Account created")
    except ValueError as error:
        parser.exit(2, str(error) + "\n")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
