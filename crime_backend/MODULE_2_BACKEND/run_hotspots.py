import asyncio
from app.scheduler.scheduled_tasks import run_hotspot_regeneration
from app.core.database import AsyncSessionLocal

async def main():
    print("Running hotspot regeneration...")
    await run_hotspot_regeneration()
    print("Done")

if __name__ == "__main__":
    asyncio.run(main())
