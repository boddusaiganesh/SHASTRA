import asyncio
from app.core.database import AsyncSessionLocal
from app.services.hotspot_service import get_time_patterns

async def test():
    async with AsyncSessionLocal() as session:
        data = await get_time_patterns(session, None, None)
        print(data)

if __name__ == "__main__":
    asyncio.run(test())
