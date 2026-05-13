from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession,create_async_engine,async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(engine,expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db()-> AsyncGenerator[AsyncSession,None]:
    async with AsyncSessionLocal() as session:
        yield session