import asyncio
import logging
from app.scheduler.scheduled_tasks import run_anomaly_detection, run_alert_detection, run_hotspot_regeneration
from app.core.database import init_db

logging.basicConfig(level=logging.INFO)

async def trigger_all():
    await init_db()
    await run_anomaly_detection()
    await run_alert_detection()
    await run_hotspot_regeneration()

if __name__ == "__main__":
    asyncio.run(trigger_all())
