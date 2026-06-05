import asyncio
import re
import ssl
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import settings — URL is used directly (bypasses configparser % escaping issues)
from src.settings import settings  # noqa: E402


def _normalize_async_url(raw: str) -> str:
    """Mirror src.db's URL handling so Alembic runs against the same engine
    config as the app. Render's connectionString is `postgresql://…` with no
    driver suffix — create_async_engine needs `+asyncpg`. Supabase/Neon URLs
    include `sslmode`/`channel_binding` query params asyncpg rejects.
    """
    url = raw
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    elif url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    url = re.sub(r"[?&](sslmode|channel_binding)=[^&]*", "", url).rstrip("?&")
    return url


_DB_URL = _normalize_async_url(settings.database_url)
_SSL_CTX = (
    ssl.create_default_context()
    if "neon.tech" in _DB_URL or "supabase" in _DB_URL
    else None
)

# Import Base and all models so autogenerate can see every table
from src.db import Base  # noqa: E402
from src.products.models import Supplier, Product  # noqa: E402, F401
from src.invoices.models import PurchaseInvoice, PurchaseInvoiceItem  # noqa: E402, F401
from src.sales.models import DailySale  # noqa: E402, F401
from src.stock.models import StockMovement  # noqa: E402, F401
from src.payments.models import Payment  # noqa: E402, F401
from src.imports.models import ImportJob  # noqa: E402, F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=_DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(
        _DB_URL,
        poolclass=pool.NullPool,
        connect_args={"ssl": _SSL_CTX} if _SSL_CTX else {},
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
