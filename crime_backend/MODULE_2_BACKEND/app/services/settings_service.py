"""Settings Service - Data source sync operations"""
from typing import Dict, Any
from datetime import datetime, timezone

async def trigger_sync(source_id: str) -> Dict[str, Any]:
    """Trigger a manual sync for a given data source. Currently a manual-trigger
    stub — wire to the real CCTNS/vehicle-registry/etc. ETL job when available."""
    return {
        "source_id": source_id,
        "status": "SYNC_QUEUED",
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }
