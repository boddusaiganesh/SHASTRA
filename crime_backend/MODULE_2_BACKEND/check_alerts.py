import asyncio
from sqlalchemy import select, func
from app.core.database import AsyncSessionLocal
from app.models.database_models.alert_model import Alert
from app.models.database_models.anomaly_model import Anomaly

async def check():
    async with AsyncSessionLocal() as session:
        alerts = await session.execute(select(func.count()).select_from(Alert))
        anomalies = await session.execute(select(func.count()).select_from(Anomaly))
        print(f"Total Alerts: {alerts.scalar()}")
        print(f"Total Anomalies: {anomalies.scalar()}")

if __name__ == "__main__":
    asyncio.run(check())
