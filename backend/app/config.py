import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite+pysqlite:///.local/timedesk.db"))
    allowed_origins: tuple[str, ...] = field(default_factory=lambda: tuple(x.strip().rstrip("/") for x in os.getenv("APP_ALLOWED_ORIGINS", "http://localhost:8095,http://127.0.0.1:8095").split(",") if x.strip()))
    cookie_secure: bool = field(default_factory=lambda: os.getenv("APP_COOKIE_SECURE", "false").lower() == "true")
    demo_mode: bool = field(default_factory=lambda: os.getenv("APP_DEMO_MODE", "false").lower() == "true")
    session_hours: int = 24
    login_limit: int = 8
    login_ip_limit: int = 64
    login_window_seconds: int = 900

    def __post_init__(self):
        if not self.allowed_origins or "*" in self.allowed_origins:
            raise ValueError("APP_ALLOWED_ORIGINS must contain exact origins")
        if min(self.session_hours, self.login_limit, self.login_ip_limit, self.login_window_seconds) <= 0:
            raise ValueError("Session and limiter settings must be positive")
