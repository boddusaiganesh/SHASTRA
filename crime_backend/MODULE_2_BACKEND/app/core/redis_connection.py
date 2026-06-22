"""
Redis Cache Connection
"""

import redis.asyncio as aioredis
from typing import Optional, Any
import json
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[aioredis.Redis] = None


async def init_redis():
    """Initialize Redis connection"""
    global _redis_client
    try:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            password=settings.REDIS_PASSWORD,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
        await _redis_client.ping()
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.warning(f"Redis connection failed (non-critical): {e}")
        _redis_client = None


async def close_redis():
    """Close Redis connection"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connection closed")


def get_redis_client() -> Optional[aioredis.Redis]:
    """Get Redis client instance"""
    return _redis_client


async def get_redis_health() -> str:
    """Check Redis health"""
    if not _redis_client:
        return "not connected"
    try:
        await _redis_client.ping()
        return "healthy"
    except Exception as e:
        return f"unhealthy: {str(e)}"


async def cache_set(key: str, value: Any, expiry: int = None) -> bool:
    """Set a value in Redis cache"""
    if not _redis_client:
        return False
    try:
        expiry = expiry or settings.CACHE_EXPIRY_SECONDS
        serialized = json.dumps(value, default=str)
        await _redis_client.setex(key, expiry, serialized)
        return True
    except Exception as e:
        logger.error(f"Redis SET error: {e}")
        return False


async def cache_get(key: str) -> Optional[Any]:
    """Get a value from Redis cache"""
    if not _redis_client:
        return None
    try:
        value = await _redis_client.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        logger.error(f"Redis GET error: {e}")
        return None


async def cache_delete(key: str) -> bool:
    """Delete a key from Redis cache"""
    if not _redis_client:
        return False
    try:
        await _redis_client.delete(key)
        return True
    except Exception as e:
        logger.error(f"Redis DELETE error: {e}")
        return False


async def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching a pattern"""
    if not _redis_client:
        return 0
    try:
        keys = await _redis_client.keys(pattern)
        if keys:
            return await _redis_client.delete(*keys)
        return 0
    except Exception as e:
        logger.error(f"Redis DELETE PATTERN error: {e}")
        return 0


async def blacklist_token(token: str, expiry: int = 28800) -> bool:
    """Add a JWT token to the blacklist"""
    return await cache_set(f"blacklisted_token:{token}", True, expiry)


async def is_token_blacklisted(token: str) -> bool:
    """Check if a JWT token is blacklisted"""
    result = await cache_get(f"blacklisted_token:{token}")
    return result is not None


async def cache_gemini_response(prompt_hash: str, response: str, expiry: int = 1800) -> bool:
    """Cache a Gemini API response for 30 minutes"""
    return await cache_set(f"gemini_cache:{prompt_hash}", response, expiry)


async def get_cached_gemini_response(prompt_hash: str) -> Optional[str]:
    """Get a cached Gemini API response"""
    return await cache_get(f"gemini_cache:{prompt_hash}")
