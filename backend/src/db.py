import re
import ssl

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from src.settings import settings

# Render's `fromDatabase.connectionString` gives `postgresql://…`, no driver
# suffix — SQLAlchemy would then fall back to psycopg2 (sync), which we don't
# ship. Force asyncpg explicitly.
_db_url = settings.database_url
if _db_url.startswith("postgresql://"):
    _db_url = "postgresql+asyncpg://" + _db_url[len("postgresql://"):]
elif _db_url.startswith("postgres://"):  # Heroku-style alias
    _db_url = "postgresql+asyncpg://" + _db_url[len("postgres://"):]

# asyncpg doesn't accept sslmode/channel_binding in the URL — strip them and pass ssl directly
_db_url = re.sub(r"[?&](sslmode|channel_binding)=[^&]*", "", _db_url)
_db_url = _db_url.rstrip("?&")

_ssl_ctx = ssl.create_default_context() if "neon.tech" in _db_url or "supabase" in _db_url else None

engine = create_async_engine(
    _db_url,
    echo=False,
    poolclass=NullPool,
    connect_args={"ssl": _ssl_ctx} if _ssl_ctx else {},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # prevents lazy-load errors after commit in async context
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass
