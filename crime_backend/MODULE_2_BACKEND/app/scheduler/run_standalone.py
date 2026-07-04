import asyncio
import logging
from app.scheduler.scheduled_tasks import init_scheduler, scheduler
from app.core.database import init_db
from app.core.redis_connection import init_redis
from app.core.neo4j_connection import init_neo4j

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_resources():
    await init_db()
    await init_redis()
    await init_neo4j()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_resources())
    
    init_scheduler()
    logger.info("Standalone APScheduler started successfully.")
    
    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
