"""Settings Service - Data source sync operations"""
from typing import Dict, Any
from datetime import datetime, timezone

async def trigger_sync(source_id: str) -> Dict[str, Any]:
    """Trigger a manual sync for a given data source."""
    if source_id in ["postgres", "neo4j"]:
        import asyncio
        from scripts.sync_postgres_to_neo4j import sync_data
        
        async def run_sync():
            try:
                await sync_data()
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Background sync failed: {e}")
                
        asyncio.create_task(run_sync())
        
    return {
        "source_id": source_id,
        "status": "SYNC_QUEUED",
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }
