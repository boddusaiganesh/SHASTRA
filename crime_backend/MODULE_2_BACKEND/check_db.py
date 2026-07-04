import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT count(*) FROM crimes"))
        print("Total crimes in DB:", result.scalar())
        
        result2 = await session.execute(text("SELECT count(*) FROM hotspots"))
        print("Total hotspots in DB:", result2.scalar())

if __name__ == "__main__":
    asyncio.run(main())
