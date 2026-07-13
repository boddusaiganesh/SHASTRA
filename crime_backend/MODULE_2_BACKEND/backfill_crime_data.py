import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.database_models.crime_model import Crime

async def test():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Crime).limit(5))
        crimes = result.scalars().all()
        for c in crimes:
            print(f"Time: {c.time_of_occurrence}, Day: {c.day_of_week}, Month: {c.month}, Year: {c.year}")

if __name__ == "__main__":
    asyncio.run(test())
