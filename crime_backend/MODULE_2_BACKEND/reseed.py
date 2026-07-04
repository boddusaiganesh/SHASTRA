import asyncio
from app.core.database import engine, Base, AsyncSessionLocal
from app.utils.data_seeder import seed_all_data

async def reset_db():
    async with engine.begin() as conn:
        print("Dropping tables...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
        
    async with AsyncSessionLocal() as session:
        print("Seeding new data...")
        await seed_all_data(session)
        print("Done!")

if __name__ == "__main__":
    asyncio.run(reset_db())
