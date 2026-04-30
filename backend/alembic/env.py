import asyncio
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

# Import Base and all models so autogenerate can see every table
from src.db import Base  # noqa: E402
from src.products.models import Supplier, Product  # noqa: E402, F401
from src.invoices.models import PurchaseInvoice, PurchaseInvoiceItem  # noqa: E402, F401
from src.sales.models import DailySale  # noqa: E402, F401
from src.stock.models import StockMovement  # noqa: E402, F401
from src.payments.models import Payment  # noqa: E402, F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
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
    # Create engine directly from settings — avoids configparser choking on % in passwords
    connectable = create_async_engine(
        settings.database_url,
        poolclass=pool.NullPool,
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
