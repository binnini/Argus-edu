from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=5,       
    max_overflow=20,
    pool_timeout=60,      
    pool_recycle=1800
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# 하위 호환 alias
SessionLocal = AsyncSessionLocal

async def get_session() -> AsyncSession:
    """FastAPI 의존성 주입용 비동기 DB 세션."""
    async with SessionLocal() as session:
        yield session