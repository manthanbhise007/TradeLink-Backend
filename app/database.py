
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import settings  # Adjust if your settings are defined elsewhere

DATABASE_URL = settings.database_url

# Ensure SQLAlchemy uses the asynchronous PostgreSQL driver
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://", "postgresql+asyncpg://", 1
    )
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)

async def get_db():
    async with SessionLocal() as session:
        yield session
