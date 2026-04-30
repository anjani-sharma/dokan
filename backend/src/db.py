from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from src.settings import settings


engine = create_async_engine(
    settings.database_url,
    echo=False,
    poolclass=NullPool,  # Supabase pooler manages connections — don't double-pool
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
