import sys
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.ml_models.crime_forecasting import CrimeForecaster

async def main():
    engine = create_async_engine("postgresql+asyncpg://postgres:postgres@localhost:5432/shastra_db")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        try:
            print("Running Prophet forecasting...")
            forecaster = CrimeForecaster(session)
            result = await forecaster.generate_forecast("KA-01", "Theft", months=3)
            print("Forecast result:")
            print(result)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
