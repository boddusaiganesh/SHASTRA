import asyncio
import random
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.database_models.crime_model import Crime

async def fix_crimes():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Crime))
        crimes = result.scalars().all()
        
        for crime in crimes:
            if crime.date_of_occurrence:
                crime.day_of_week = crime.date_of_occurrence.strftime('%A')
                crime.month = crime.date_of_occurrence.month
                crime.year = crime.date_of_occurrence.year
            
            # Generate realistic times (mostly evening/night for crimes, but some daytime)
            hour = int(random.choices(
                population=[*range(0,24)],
                weights=[3, 4, 3, 2, 1, 1, 1, 2, 3, 4, 5, 5, 4, 4, 5, 6, 7, 8, 9, 10, 10, 8, 6, 4],
                k=1
            )[0])
            minute = random.choice([0, 15, 30, 45, random.randint(0,59)])
            crime.time_of_occurrence = f"{hour:02d}:{minute:02d}"
        
        print(f"Updating {len(crimes)} crimes...")
        await session.commit()
        print("Done!")

if __name__ == "__main__":
    asyncio.run(fix_crimes())
