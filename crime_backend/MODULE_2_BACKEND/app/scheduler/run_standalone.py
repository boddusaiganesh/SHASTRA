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

import os
import uvicorn
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "Scheduler is running healthy"}

async def run_server():
    port = int(os.getenv("X_ZOHO_CATALYST_LISTEN_PORT", 8080))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await init_resources()
    init_scheduler()
    logger.info("Standalone APScheduler started successfully.")
    await run_server()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
